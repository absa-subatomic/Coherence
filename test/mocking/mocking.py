class MockRequestsResponse:
    def __init__(self, json_data="", status_code=200, content=""):
        self.json_data = json_data
        self.status_code = status_code
        self.content = content

    def json(self):
        return self.json_data
