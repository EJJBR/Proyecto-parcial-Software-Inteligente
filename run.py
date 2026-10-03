"""Punto de entrada local para la aplicación Flask."""
from app import create_app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", debug=False)
