# Lambda Treasure Hunt Player

- [x] Build and save the map 
- [x] Pick up treasure
- [x] Don wearable items
- [x] Sell treasure
- [x] Change name
- [x] Pray at shrines
- [x] Fly
- [x] Dash

To do:
- [ ] Mine and proof
- [ ] Transmogrify
- [ ] Warp
- [ ] Get golden snitches

## To play:
Start a [test server](https://github.com/LambdaSchool/Lambda-Treasure-Hunt--Test).
- `$ python3 manage.py makemigrations`
- `$ python3 manage.py migrate`
- `$ python3 manage.py shell`

In the test server shell:
- `>>> from util import create_world`

Open another terminal window, CD to the test directory, and do:
- `$ python3 manage.py runserver`

In a third terminal window:
CD to this directory, start the pipenv shell, then:
- `$ python`
- `>>> from play_it import GamePlayer`
- `>>> game = GamePlayer()`
- `>>> game.get_key()`

Return to test server shell:
- `>>> from adventure.models import Game, Player`
- `>>> p = Player.objects.get(name='testuser')`
- `>>> g = Group.objects.get(name='test')`
- `>>> p.group = g`
- `>>> p.save()`

Back in this shell:
- `>>> game.auto_play()`
