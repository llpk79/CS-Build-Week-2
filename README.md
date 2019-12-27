# Lambda Treasure Hunt Player

So far it builds the map, picks up treasures, and dons wearable items.

## To play:
Start a test server found [here](https://github.com/LambdaSchool/Lambda-Treasure-Hunt--Test).
- `$ python3 manage.py makemigrations`
- `$ python3 manage.py migrate`
- `$ python3 manage.py shell`

In the test server shell:
- `>>> from util import create_world`

Open another terminal window to do:
- `$ python3 manage.py, runserver`

In a third terminal window:
CD to this directory, start the pipenv shell, then:
- `$ python`
- `>>> from play_it import GamePlayer`
- `>>> game = GamePlayer()`
- `>>> game.get_key()`

Return to test server shell:
- `>>> from adventure.models import Game, Player`
- `>>> p = Player.objects.all()`
- `>>> p = p[len(p) - 1]  # -1 indexing doesn't work here.`
- `>>> g = Group.objects.get(name='test')`
- `>>> p.group = g`
- `>>> p.save()`

Back in this shell:
- `>>> game.initialize_player()`
- `>>> game.traverse_map()`
