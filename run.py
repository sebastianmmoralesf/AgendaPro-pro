import os
from project import create_app

app = create_app()

if __name__ == '__main__':
    # En desarrollo local
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
else:
    # En producción (Gunicorn)
    # Gunicorn se encarga de manejar el servidor
