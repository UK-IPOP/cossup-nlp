import httpx


def box_auth() -> str:
    url = "https://account.box.com/api/oauth2/authorize?response_type=code&client_id=ly1nj6n11vionaie65emwzk575hnnmrk&redirect_uri=http://example.com/auth/callback"
    print(f"Go to {url} and paste the code here:")
    code = input()
    return ""


def box_download_file(id: str, token: str) -> bytes:
    resp = httpx.get(
        f"https://api.box.com/2.0/files/{id}/content",
        headers={"authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.content


def main():
    token = box_auth()
    file = box_download_file("123", token)
    print(file)


if __name__ == "__main__":
    main()
