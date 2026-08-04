# seed.py
from database import get_session, Character, Anime

def seed_if_empty():
    db = get_session()
    if db.query(Character).count() > 0:
        print("📦 БД уже заполнена")
        db.close()
        return

    print("🌱 Загружаем начальных персонажей...")

    DATA = [
        ("Naruto", "Наруто", [
            ("Naruto Uzumaki", "Наруто Узумаки", "legendary", 95, 70, 85),
            ("Sasuke Uchiha", "Саске Учиха", "legendary", 93, 75, 90),
            ("Sakura Haruno", "Сакура Харуно", "epic", 80, 65, 70),
            ("Kakashi Hatake", "Какаши Хатаке", "legendary", 90, 80, 88),
            ("Itachi Uchiha", "Итачи Учиха", "mythical", 97, 85, 92),
            ("Hinata Hyuga", "Хината Хьюга", "epic", 72, 68, 75),
            ("Rock Lee", "Рок Ли", "rare", 85, 60, 95),
            ("Gaara", "Гаара", "legendary", 88, 95, 65),
            ("Jiraiya", "Джирайя", "mythical", 92, 78, 80),
            ("Minato Namikaze", "Минато Намикадзе", "mythical", 95, 78, 100),
            ("Shikamaru Nara", "Шикамару Нара", "rare", 55, 50, 60),
            ("Neji Hyuga", "Нэдзи Хьюга", "rare", 82, 78, 85),
            ("Tenten", "Тентен", "uncommon", 65, 55, 70),
            ("Kiba Inuzuka", "Киба Инузука", "uncommon", 68, 52, 78),
            ("Konohamaru", "Конохамару", "common", 45, 40, 55),
            ("Iruka Umino", "Ирука Умино", "common", 40, 45, 50),
        ]),
        ("Attack on Titan", "Атака титанов", [
            ("Levi Ackerman", "Леви Аккерман", "mythical", 99, 85, 99),
            ("Eren Yeager", "Эрен Йегер", "legendary", 94, 80, 78),
            ("Mikasa Ackerman", "Микаса Аккерман", "legendary", 96, 82, 93),
            ("Erwin Smith", "Эрвин Смит", "legendary", 78, 70, 72),
            ("Armin Arlert", "Армин Арлерт", "epic", 60, 45, 55),
            ("Hange Zoe", "Ханджи Зоэ", "epic", 72, 65, 70),
            ("Annie Leonhart", "Энни Леонхарт", "legendary", 88, 90, 85),
            ("Jean Kirstein", "Жан Кирштайн", "rare", 70, 65, 72),
            ("Sasha Blouse", "Саша Браус", "rare", 68, 55, 80),
            ("Connie Springer", "Конни Спрингер", "uncommon", 60, 50, 75),
            ("Marco Bott", "Марко Ботт", "common", 50, 50, 55),
        ]),
        ("Jujutsu Kaisen", "Магическая битва", [
            ("Satoru Gojo", "Сатору Годжо", "secret", 100, 100, 95),
            ("Ryomen Sukuna", "Рёмен Сукуна", "secret", 100, 98, 97),
            ("Yuji Itadori", "Юдзи Итадори", "legendary", 90, 80, 88),
            ("Megumi Fushiguro", "Мегуми Фушигуро", "legendary", 85, 75, 82),
            ("Nobara Kugisaki", "Нобара Кугисаки", "epic", 78, 65, 75),
            ("Yuta Okkotsu", "Юта Оккоцу", "mythical", 95, 88, 85),
            ("Kento Nanami", "Кэнто Нанами", "legendary", 88, 82, 78),
            ("Toge Inumaki", "Тогэ Инумаки", "epic", 72, 55, 70),
            ("Maki Zenin", "Маки Дзэнин", "epic", 82, 78, 85),
            ("Panda", "Панда", "rare", 80, 85, 65),
            ("Aoi Todo", "Аой Тодо", "epic", 90, 78, 80),
        ]),
        ("Demon Slayer", "Истребитель демонов", [
            ("Muzan Kibutsuji", "Музан Кибуцуджи", "secret", 100, 95, 90),
            ("Tanjiro Kamado", "Танджиро Камадо", "legendary", 88, 75, 85),
            ("Nezuko Kamado", "Нэзуко Камадо", "legendary", 82, 90, 80),
            ("Rengoku Kyojuro", "Ренгоку Кёджуро", "mythical", 95, 80, 90),
            ("Zenitsu Agatsuma", "Зеницу Агацума", "epic", 75, 50, 98),
            ("Inosuke Hashibira", "Иноскэ Хашибира", "epic", 83, 72, 82),
            ("Giyu Tomioka", "Гию Томиока", "legendary", 90, 85, 88),
            ("Shinobu Kocho", "Шинобу Кочо", "legendary", 78, 60, 95),
            ("Kanao Tsuyuri", "Канао Цуюри", "epic", 80, 72, 88),
            ("Muichiro Tokito", "Муичиро Токито", "legendary", 85, 70, 92),
        ]),
        ("One Piece", "Ван Пис", [
            ("Monkey D. Luffy", "Монки Д. Луффи", "mythical", 97, 85, 90),
            ("Shanks", "Шанкс", "secret", 99, 92, 95),
            ("Kaido", "Кайдо", "secret", 100, 100, 75),
            ("Roronoa Zoro", "Ророноа Зоро", "legendary", 95, 88, 82),
            ("Sanji", "Санджи", "legendary", 90, 75, 92),
            ("Nami", "Нами", "epic", 55, 45, 70),
            ("Portgas D. Ace", "Портгас Д. Эйс", "mythical", 92, 75, 88),
            ("Boa Hancock", "Боа Хэнкок", "legendary", 88, 80, 85),
            ("Usopp", "Усопп", "rare", 50, 40, 65),
            ("Tony Tony Chopper", "Чоппер", "rare", 60, 55, 58),
            ("Nico Robin", "Нико Робин", "epic", 70, 60, 65),
            ("Franky", "Фрэнки", "rare", 75, 82, 55),
            ("Brook", "Брук", "rare", 65, 50, 78),
        ]),
    ]

    total = 0
    for title_en, title_ru, chars in DATA:
        anime = Anime(title_en=title_en, title_ru=title_ru)
        db.add(anime)
        db.flush()
        for name_en, name_ru, rarity, power, defense, speed in chars:
            db.add(Character(
                name_en=name_en, name_ru=name_ru, anime_id=anime.id,
                rarity=rarity, power=power, defense=defense, speed=speed,
            ))
            total += 1

    db.commit()
    db.close()
    print(f"✅ Загружено {total} персонажей!")