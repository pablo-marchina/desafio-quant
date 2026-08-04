import requests

QDRANT_URL = "http://localhost:6333"

def main() -> int:
    try:
        response = requests.get(QDRANT_URL, timeout=5)
        response.raise_for_status()

        print("Qdrant está online.")
        print("Resposta:")
        print(response.json())
        return 0

    except requests.exceptions.ConnectionError:
        print("Erro: não foi possível conectar ao Qdrant.")
        print("Verifique se o Docker Desktop está aberto e se o container está rodando.")
        print("Comando para subir o Qdrant:")
        print("docker compose up -d")
        return 1

    except requests.exceptions.RequestException as error:
        print("Erro ao consultar o Qdrant:")
        print(error)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
