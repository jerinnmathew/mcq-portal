from backend import create_app

# Instantiate the Flask application using our application factory pattern
app = create_app()

if __name__ == '__main__':
    # Start the local development server
    print("--------------------------------------------------")
    print("SEA-1 MCQ Battle Platform is launching!")
    print("Access the portal at: http://localhost:5005")
    print("--------------------------------------------------")
    app.run(host="0.0.0.0", port=5005, debug=False)
