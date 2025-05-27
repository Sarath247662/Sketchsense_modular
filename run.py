# run.py

from app import create_app

app = create_app()

if __name__ == "__main__":
    # dev server
    app.run(host="0.0.0.0", port=5003, debug=True)
