#!/usr/bin/env bash
# ==============================================================================
# Declarative Installer for Betterleaks Open-WebUI Inlet Filter
# ==============================================================================
set -euo pipefail

FILTER_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/openwebui_filter.py"

if [ ! -f "$FILTER_FILE" ]; then
    echo "Error: Filter file not found at $FILTER_FILE" >&2
    exit 1
fi

echo "Copying $FILTER_FILE into open-webui container..."
docker cp "$FILTER_FILE" open-webui:/tmp/openwebui_filter.py

echo "Registering filter in Open-WebUI database..."
docker exec open-webui python3 -c "
import asyncio
from open_webui.models.functions import Functions, FunctionForm, FunctionMeta
from open_webui.models.users import Users

async def install_filter():
    admin = await Users.get_first_user()
    if not admin:
        print('Error: No admin user found in Open-WebUI database.')
        exit(1)

    with open('/tmp/openwebui_filter.py', 'r', encoding='utf-8') as f:
        content = f.read()

    func_id = 'betterleaks_guard'
    func_name = 'Betterleaks & Presidio Secret Guard'

    existing = await Functions.get_function_by_id(func_id)
    if existing:
        await Functions.update_function_by_id(
            func_id,
            {
                'name': func_name,
                'content': content,
                'is_active': True,
                'is_global': True,
            }
        )
        print(f'Successfully updated existing filter: {func_id}')
    else:
        form = FunctionForm(
            id=func_id,
            name=func_name,
            content=content,
            meta=FunctionMeta(
                description='Real-time secret & PII redaction filter using Betterleaks and Presidio',
                manifest={}
            )
        )
        res = await Functions.insert_new_function(admin.id, 'filter', form)
        await Functions.update_function_by_id(func_id, {'is_active': True, 'is_global': True})
        print(f'Successfully registered and enabled new filter: {res.id}')

asyncio.run(install_filter())
"

echo "Open-WebUI filter installation complete."
