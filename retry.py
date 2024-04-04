from boxsdk import OAuth2, Client

auth = OAuth2(
    client_id="a7xemajr8s5kxazb1gf2jw9eciey8rdg",
    client_secret="v7Rdd9qqcSOpFk79PYScMy4svnBMQuRf",
    access_token="sJEjSlCG1E4hojdC72JbX4zFhEW4HmJr",
)
client = Client(auth)

user = client.user().get()
print(f"The current user ID is {user.id}")

client.as_user(user)

folder = client.folder("253335392903").get()
print(folder)
for item in folder.get_items():
    print(item)
    if item.type != "file":
        continue
    file_data = client.file(item.id).content()
    print(len(file_data))
