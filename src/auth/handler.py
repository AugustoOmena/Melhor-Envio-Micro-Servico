import json


def lambda_handler(event, context):
    # ESSA LINHA É A MAIS IMPORTANTE AGORA
    print("EVENTO RECEBIDO:", json.dumps(event))

    # Vamos pegar o path de onde quer que ele venha (HTTP API v2 ou REST v1)
    raw_path = event.get("rawPath") or event.get("path")
    print(f"PATH DETECTADO: {raw_path}")

    # Se o Powertools estiver falhando, esse IF vai nos salvar
    if raw_path and "authorize-url" in raw_path:
        # Lógica mínima para teste
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({
                "authorize_url": "https://sandbox.melhorenvio.com.br/...",
                "debug_path": raw_path,
            }),
        }

    return {
        "statusCode": 404,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({"error": "Rota não encontrada na Lambda", "path_received": raw_path}),
    }
