def handler(request):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/plain"},
        "body": "API is working!"
    }