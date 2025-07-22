import requests
import sys
import time

def test_root_redirect():
    """Test that root URL redirects to chat endpoint"""
    print("\nTesting root URL redirect...")
    response = requests.get('http://127.0.0.1:8000/', allow_redirects=False)
    if response.status_code == 302 and response.headers['Location'] == '/api/v1/triple/chat/':
        print("✅ Root URL redirect test passed")
    else:
        print("❌ Root URL redirect test failed")
        print(f"Expected status code 302, got {response.status_code}")
        print(f"Expected Location header '/api/v1/triple/chat/', got {response.headers.get('Location', 'no Location header')}")

def test_chat_endpoint():
    """Test the chat API endpoint"""
    print("\nTesting chat API endpoint...")
    data = {"topic": "Test topic"}
    response = requests.post('http://127.0.0.1:8000/api/v1/triple/chat/', json=data)
    
    if response.status_code == 200:
        print("✅ Chat API test passed")
        print(f"Response: {response.json()}")
    else:
        print("❌ Chat API test failed")
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.text}")

def main():
    print("Starting backend API tests...")
    try:
        test_root_redirect()
        test_chat_endpoint()
        print("\nAll tests completed!")
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to the backend server")
        print("Make sure the Django server is running on http://127.0.0.1:8000")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during testing: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()