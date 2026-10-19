{{ with secret "secret/data/llm-stack/seaweedfs" }}
{
  "identities": [
    {
      "name": "seaweed_admin",
      "credentials": [
        {
          "accessKey": "{{ .Data.data.S3_ACCESS_KEY }}",
          "secretKey": "{{ .Data.data.S3_SECRET_KEY }}"
        }
      ],
      "actions": [
        "Read",
        "Write",
        "List",
        "Tagging",
        "Admin"
      ]
    },
    {
      "name": "langfuse_app",
      "credentials": [
        {
          "accessKey": "{{ .Data.data.LANGFUSE_S3_ACCESS_KEY }}",
          "secretKey": "{{ .Data.data.LANGFUSE_S3_SECRET_KEY }}"
        }
      ],
      "actions": [
        "Read:langfuse",
        "Write:langfuse",
        "List:langfuse",
        "Tagging:langfuse"
      ]
    }
  ]
}
{{ end }}
