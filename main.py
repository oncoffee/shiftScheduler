from dotenv import load_dotenv
import uvicorn

load_dotenv()

if __name__ == '__main__':
    uvicorn.run("app:app",
                host="192.168.1.228",
                port=1900,
                reload=True)