from app.dataset_routes import search_dataset


class FakeUser:
    id = 1
    username = "testuser"


def run():
    res = search_dataset(q="Beyonce", top_k=5, current_user=FakeUser())
    print(res)


if __name__ == '__main__':
    run()
