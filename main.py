from box_sdk_gen import BoxClient, BoxDeveloperTokenAuth

folder_id = "253335392903"


def main(token: str):
    auth: BoxDeveloperTokenAuth = BoxDeveloperTokenAuth(token=token)
    client: BoxClient = BoxClient(auth=auth)
    for item in client.folders.get_folder_items("0").entries:
        if item.type != "file":
            continue
        file_info = client.files.get_file_by_id(file_id=item.id)
        print(file_info.name)
        with open(file_info.name, "wb") as f:
            f.write(client.downloads.download_file(file_id=file_info.id))
    # -----
    # for item in client.folders.get_folder_items(folder_id=folder_id).entries:
    #     file_info = client.files.get_file_by_id(file_id=item.id)
    #     with open(file_info.name, "wb") as f:
    #         f.write(client.downloads.download_file(file_id=file_info.id))


if __name__ == "__main__":
    main("6pKbf5tRHhBupkO3M9unpnAQY31QQgOS")
