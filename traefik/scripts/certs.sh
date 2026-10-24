#!/usr/bin/env bash
# ==============================================================================
# TLS material for the stack, called by ../../setup.sh (inputs from the environment):
#   DOMAIN         stack domain (required)
#   TLS_MODE       internal (default) | custom | http-01 | cloudflare-dns01
#   TLS_CSR_REGEN  "true" to generate a new key and CSR for your CA (custom.key/custom.csr),
#                  without changing the certificate currently served
# Exit codes: 0 ready, 1 invalid material, 2 custom-mode CSR waiting to be signed.
# ==============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_DIR"

: "${DOMAIN:?DOMAIN must be set}"
TLS_MODE="${TLS_MODE:-internal}"
TLS_CSR_REGEN="${TLS_CSR_REGEN:-false}"
CERT_DIR="traefik/certs"

# ------------------------------------------------------------------------------
# TLS material (traefik/certs/, gitignored). Two independent trust chains:
#   * internal-ca.crt/.key  local CA, always generated; signs vault.crt (Vault listener,
#                           SANs vault/localhost/127.0.0.1) and, in internal mode, tls.crt.
#   * tls.crt/.key + ca.crt ingress certificate served by Traefik for DOMAIN and *.DOMAIN,
#                           and the CA chain that clients behind Traefik must trust. In custom
#                           mode they are installed from custom.crt/custom.key/custom-ca.crt
#                           (key and CSR generated here, certificate signed by your CA).
# ------------------------------------------------------------------------------

# Issue a leaf certificate signed by the local CA: issue_internal_leaf <name> <CN> <SANs>
issue_internal_leaf() {
    local name="$1" cn="$2" sans="$3" ext
    ext="$(mktemp)"
    # Key identifiers are required by strict X.509 verification (Python >= 3.13 default).
    printf 'subjectAltName=%s\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=serverAuth\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid:always\n' "$sans" > "$ext"
    openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$CERT_DIR/$name.key" 2>/dev/null
    openssl req -new -key "$CERT_DIR/$name.key" -subj "/CN=${cn}" 2>/dev/null \
        | openssl x509 -req -CA "$CERT_DIR/internal-ca.crt" -CAkey "$CERT_DIR/internal-ca.key" \
            -set_serial "0x$(openssl rand -hex 16)" -days 825 -sha256 -extfile "$ext" \
            -out "$CERT_DIR/$name.crt" 2>/dev/null
    rm -f "$ext"
    chmod 644 "$CERT_DIR/$name.key" "$CERT_DIR/$name.crt"
}

# True when the certificate covers DOMAIN and *.DOMAIN.
cert_covers_domain() {
    local sans
    sans="$(openssl x509 -in "$1" -noout -ext subjectAltName 2>/dev/null)"
    [[ "$sans" == *"DNS:${DOMAIN},"* || "$sans" == *"DNS:${DOMAIN}" ]] && [[ "$sans" == *"DNS:*.${DOMAIN}"* ]]
}

ensure_internal_ca() {
    mkdir -p "$CERT_DIR"
    if [ ! -f "$CERT_DIR/internal-ca.crt" ] || [ ! -f "$CERT_DIR/internal-ca.key" ]; then
        echo "Generating the stack's internal certificate authority..."
        openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$CERT_DIR/internal-ca.key" 2>/dev/null
        openssl req -x509 -new -key "$CERT_DIR/internal-ca.key" -sha256 -days 3650 \
            -subj "/CN=LLM Stack Internal CA (${DOMAIN})" \
            -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
            -addext "keyUsage=critical,keyCertSign,cRLSign" \
            -addext "subjectKeyIdentifier=hash" \
            -out "$CERT_DIR/internal-ca.crt" 2>/dev/null
        chmod 644 "$CERT_DIR/internal-ca.crt"
        chmod 600 "$CERT_DIR/internal-ca.key"
        # Anything signed by a previous CA (or the legacy self-signed certificate) is reissued.
        rm -f "$CERT_DIR/vault.crt" "$CERT_DIR/vault.key"
        [ "${TLS_MODE}" = "internal" ] && rm -f "$CERT_DIR/tls.crt" "$CERT_DIR/tls.key"
    fi
    if [ ! -f "$CERT_DIR/vault.crt" ] || [ ! -f "$CERT_DIR/vault.key" ] \
        || ! openssl verify -x509_strict -CAfile "$CERT_DIR/internal-ca.crt" "$CERT_DIR/vault.crt" >/dev/null 2>&1; then
        echo "Issuing the internal Vault listener certificate..."
        issue_internal_leaf vault vault "DNS:vault,DNS:localhost,IP:127.0.0.1"
    fi
}

ensure_ingress_certificate() {
    case "${TLS_MODE}" in
        internal)
            if [ -f "$CERT_DIR/tls.crt" ] && [ -f "$CERT_DIR/tls.key" ] && cert_covers_domain "$CERT_DIR/tls.crt" \
                && openssl verify -x509_strict -CAfile "$CERT_DIR/internal-ca.crt" "$CERT_DIR/tls.crt" >/dev/null 2>&1; then
                echo "Preserving the existing internal ingress certificate for ${DOMAIN}."
            else
                echo "Issuing the internal ingress certificate for ${DOMAIN} and *.${DOMAIN}..."
                issue_internal_leaf tls "${DOMAIN}" "DNS:${DOMAIN},DNS:*.${DOMAIN}"
            fi
            cp "$CERT_DIR/internal-ca.crt" "$CERT_DIR/ca.crt"
            ;;
        custom)
            if [ ! -f "$CERT_DIR/custom.key" ]; then
                generate_custom_csr
            fi
            if [ ! -f "$CERT_DIR/custom.crt" ] || [ ! -f "$CERT_DIR/custom-ca.crt" ]; then
                print_custom_instructions
                exit 2
            fi
            validate_custom_certificate
            install -m 644 "$CERT_DIR/custom.crt" "$CERT_DIR/tls.crt"
            install -m 644 "$CERT_DIR/custom.key" "$CERT_DIR/tls.key"
            install -m 644 "$CERT_DIR/custom-ca.crt" "$CERT_DIR/ca.crt"
            ;;
        http-01|cloudflare-dns01)
            # Traefik obtains the ingress certificate from ACME; clients use the system trust store.
            rm -f "$CERT_DIR/ca.crt"
            ;;
    esac
    # Host-side scripts reach both Vault (internal CA) and services behind Traefik (ingress CA).
    cat "$CERT_DIR/internal-ca.crt" > "$CERT_DIR/trust.crt"
    if [ -f "$CERT_DIR/ca.crt" ] && ! cmp -s "$CERT_DIR/ca.crt" "$CERT_DIR/internal-ca.crt"; then
        cat "$CERT_DIR/ca.crt" >> "$CERT_DIR/trust.crt"
    fi
    # Compose mounts ca.crt unconditionally; in ACME modes it holds the internal CA only.
    [ -f "$CERT_DIR/ca.crt" ] || cp "$CERT_DIR/internal-ca.crt" "$CERT_DIR/ca.crt"
    chmod 644 "$CERT_DIR/ca.crt" "$CERT_DIR/trust.crt"
}

# Key and CSR for your own CA. Kept apart from tls.key/tls.crt so a running stack is not
# affected until the signed certificate is installed with --tls-mode=custom.
generate_custom_csr() {
    echo "Generating an ECDSA P-256 key and certificate signing request for ${DOMAIN}..."
    mkdir -p "$CERT_DIR"
    openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$CERT_DIR/custom.key" 2>/dev/null
    chmod 644 "$CERT_DIR/custom.key"
    openssl req -new -key "$CERT_DIR/custom.key" -sha256 -subj "/CN=${DOMAIN}" \
        -addext "subjectAltName=DNS:${DOMAIN},DNS:*.${DOMAIN}" \
        -out "$CERT_DIR/custom.csr" 2>/dev/null
    rm -f "$CERT_DIR/custom.crt"
}

print_custom_instructions() {
    echo "========================================================================"
    echo " Submit ${CERT_DIR}/custom.csr to your certificate authority."
    echo "   Subject: CN=${DOMAIN}   SANs: ${DOMAIN}, *.${DOMAIN}"
    echo " Then place:"
    echo "   ${CERT_DIR}/custom.crt     the signed certificate followed by any intermediates"
    echo "   ${CERT_DIR}/custom-ca.crt  your CA chain (intermediates and root)"
    echo " and run ./setup.sh --tls-mode=custom to validate and install them."
    echo "========================================================================"
}

# Strict X.509 verification in OpenSSL >= 3.2 (and therefore Python >= 3.13 linked against it)
# requires an Authority Key Identifier on every non-self-signed certificate and a Subject Key
# Identifier on every CA certificate. Older OpenSSL releases do not enforce this with
# -x509_strict, so it is checked explicitly here, whatever OpenSSL runs setup.sh.
check_key_identifiers() {
    local pem_file split_dir part subject issuer
    split_dir="$(mktemp -d)"
    for pem_file in "$@"; do
        awk -v dir="$split_dir" -v base="$(basename "$pem_file")" \
            '/-----BEGIN CERTIFICATE-----/{n++} n{print > (dir "/" base "." n ".pem")}' "$pem_file"
    done
    for part in "$split_dir"/*.pem; do
        subject="$(openssl x509 -in "$part" -noout -subject -nameopt RFC2253 | sed 's/^subject=//')"
        issuer="$(openssl x509 -in "$part" -noout -issuer -nameopt RFC2253 | sed 's/^issuer=//')"
        if [ "$subject" != "$issuer" ] && ! openssl x509 -in "$part" -noout -ext authorityKeyIdentifier 2>/dev/null | grep -q 'Authority Key Identifier'; then
            echo "ERROR: certificate \"${subject}\" has no Authority Key Identifier; strict TLS clients (Python >= 3.13) reject it." >&2
            rm -rf "$split_dir"
            exit 1
        fi
        if openssl x509 -in "$part" -noout -ext basicConstraints 2>/dev/null | grep -q 'CA:TRUE' \
            && ! openssl x509 -in "$part" -noout -ext subjectKeyIdentifier 2>/dev/null | grep -q 'Subject Key Identifier'; then
            echo "ERROR: CA certificate \"${subject}\" has no Subject Key Identifier; strict TLS clients (Python >= 3.13) reject it." >&2
            rm -rf "$split_dir"
            exit 1
        fi
    done
    rm -rf "$split_dir"
}

validate_custom_certificate() {
    local cert="$CERT_DIR/custom.crt" key="$CERT_DIR/custom.key" ca="$CERT_DIR/custom-ca.crt"
    if [ "$(openssl x509 -in "$cert" -noout -pubkey 2>/dev/null)" != "$(openssl pkey -in "$key" -pubout 2>/dev/null)" ]; then
        echo "ERROR: ${cert} does not match ${key} (was it issued for the current CSR?)." >&2
        exit 1
    fi
    if ! cert_covers_domain "$cert"; then
        echo "ERROR: ${cert} must cover ${DOMAIN} and *.${DOMAIN} in its subjectAltName." >&2
        exit 1
    fi
    check_key_identifiers "$cert" "$ca"
    if ! openssl verify -x509_strict -CAfile "$ca" -untrusted "$cert" "$cert" >/dev/null 2>&1; then
        echo "ERROR: ${cert} does not chain to ${ca} under strict X.509 checks, which Python >= 3.13" >&2
        echo "       applies (e.g. missing Authority/Subject Key Identifiers):" >&2
        openssl verify -x509_strict -CAfile "$ca" -untrusted "$cert" "$cert" 2>&1 | grep -m1 'error' >&2 || true
        exit 1
    fi
    if ! openssl x509 -in "$cert" -noout -checkend 0 >/dev/null; then
        echo "ERROR: ${cert} has expired." >&2
        exit 1
    fi
    if ! openssl x509 -in "$cert" -noout -checkend 2592000 >/dev/null; then
        echo "WARNING: ${cert} expires within 30 days ($(openssl x509 -in "$cert" -noout -enddate | cut -d= -f2))."
    fi
    echo "Custom ingress certificate validated ($(openssl x509 -in "$cert" -noout -issuer | sed 's/^issuer=//'))."
}

ensure_internal_ca
if [ "$TLS_CSR_REGEN" = true ]; then
    generate_custom_csr
    [ "$TLS_MODE" = "custom" ] || print_custom_instructions
fi
ensure_ingress_certificate
