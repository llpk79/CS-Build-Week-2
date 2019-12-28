import pickle
import random
import requests
from collections import deque
from datetime import datetime

URL = 'http://localhost:8000/'


class GamePlayer:
    """Plays the Lambda Treasure Hunt game."""

    def __init__(self):
        self.key = None
        self.auth = None
        self.cooldown = 0
        self.world = {}
        self.current_room = 0
        self.then = datetime.now()
        self.strength = 0
        self.encumbrance = 0
        self.encumbered = False
        self.speed = 0
        self.status_ = []
        self.gold = 0
        self.bodywear = None
        self.footwear = None
        self.places = {'shop': None, 'shrine': {}, 'mine': None, 'transmogrifier': None, 'changer': None}
        self.items = deque()

    def make_request(self, suffix: str, http: str, data: dict = None, header: dict = None) -> dict:
        """Make API request to game server, return json response."""
        # Wait for cooldown period to expire.
        while (datetime.now() - self.then).seconds < self.cooldown + .001:
            pass
        if http == 'get':
            response = requests.get(URL + suffix, headers=header, data=data)
        elif http == 'post':
            response = requests.post(URL + suffix, headers=header, json=data)

        response.raise_for_status()  # If status 4xx or 5xx, raise error.
        response = response.json()

        # Handle response.
        if 'cooldown' in response:
            self.cooldown = int(response['cooldown'])
        if 'errors' in response:
            if response['errors']:
                print(f'\nError: {response["errors"]}')
        if 'messages' in response:
            if response['messages']:
                print(f'\n{" ".join(response["messages"])}')

        self.then = datetime.now()  # Reset timer.
        return response

    def get_key(self) -> None:
        """Register a Player, get/set api key, set authorization dict."""
        form = {"username": "Paulus1",
                "password1": "testpassword",
                "password2": "testpassword"}
        header = {"Content-Type": "application/json"}
        response = self.make_request(suffix='api/registration/', header=header, data=form, http='post')
        if 'key' in response:
            key = response['key']
            self.key = key
            self.auth = {"Authorization": f"Token {self.key}",
                         "Content-Type": "application/json"}
        # return response

    def initialize_player(self) -> None:
        """Create player in server database and initialize world map."""
        header = {"Authorization": f"Token {self.key}"}
        response = self.make_request(suffix='api/adv/init/', header=header, http='get')
        self.world[self.current_room] = {'meta': response,
                                         'to_n': None,
                                         'to_w': None,
                                         'to_s': None,
                                         'to_e': None}
        self.status()
        print(f'\nIn room {self.current_room}')
        if 'items' in response:
            for item in response['items']:
                self.take(item)
        return

    def get_exits(self, room: int) -> list:
        """Return list of all exits from <room>."""
        return self.world[room]['meta']['exits']

    def BFS_UE(self) -> list:
        """Create path to nearest unexplored exit."""
        visited = set()
        queue = deque()
        path = (self.current_room, '')
        queue.append([path])

        while queue:
            path = queue.popleft()
            room = path[-1][0]
            if room not in visited:
                visited.add(room)
                exits = self.get_exits(room)
                # Stop if any exit is unexplored.
                if any([self.world[room][f'to_{exit_}'] is None for exit_ in exits]):
                    return path[1:]  # Omit the room we're already in.
                # Add a new path to the queue for each exit.
                for exit_ in exits:
                    new_room = self.world[room][f'to_{exit_}']
                    new_path = [*path, (new_room, exit_)]
                    queue.append(new_path)

    def DFS_DE(self) -> None:
        """Take first available unexplored exit until there are no unexplored exits."""
        rev_dir = {'n': 's', 'w': 'e', 's': 'n', 'e': 'w'}
        while True:
            exits = self.get_exits(self.current_room)

            # If we've explored all exits, time to BFS.
            if all([self.world[self.current_room][f'to_{exit_}'] is not None for exit_ in exits]):
                return

            # Get all unexplored exits.
            open_exits = [d for d in exits if self.world[self.current_room][f'to_{d}'] is None]

            # Take the first open path.
            open_exit = open_exits[0]
            new_room = self.move(open_exit)
            new_room_id = int(new_room['room_id'])

            # Mark new rooms and connections on our map.
            if new_room_id not in self.world:
                self.world[new_room_id] = {'meta': new_room,
                                           'to_n': None,
                                           'to_w': None,
                                           'to_s': None,
                                           'to_e': None}
            self.world[self.current_room][f'to_{open_exit}'] = new_room_id
            self.world[new_room_id][f'to_{rev_dir[open_exit]}'] = self.current_room

            # Mark all non-exits.
            for exit_ in ['n', 'w', 's', 'e']:
                if exit_ not in exits:
                    self.world[self.current_room][f'to_{exit_}'] = False

            # Update our current place in the map.
            self.current_room = new_room_id

    def take_path(self, path: list) -> None:
        """Move along the <path> created by BFS to find the nearest room with an unexplored exit."""
        for next_room in path:
            room = next_room[0]
            direction = next_room[1]
            new_room = self.move(direction, room=room)
            self.current_room = int(new_room['room_id'])

    def traverse_map(self) -> None:
        """Do a DFS to dead-end, BFS to an unexplored exit to create world map."""
        print('\nChecking if map saved...')
        try:
            with open('world.pickle', 'rb') as f:
                self.world = pickle.load(f)
            print('Map complete!\n')
        except FileNotFoundError:
            print('\nBuilding map...')
            while True:
                self.DFS_DE()
                more_to_explore = self.BFS_UE()
                if not more_to_explore:
                    print('Map complete!\n')
                    with open('world.pickle', 'wb') as f:
                        pickle.dump(self.world, f)
                    return
                self.take_path(more_to_explore)
                print(f'{len(self.world)} rooms found!')

    def move_to(self, target) -> list:
        """Create a path to a <target> room."""
        if self.current_room == target:
            return []
        visited = set()
        path = [(self.current_room, '')]
        queue = deque()
        queue.append(path)
        while queue:
            path = queue.popleft()
            room = path[-1][0]
            if room not in visited:
                visited.add(room)
                exits = self.get_exits(room)
                for exit_ in exits:
                    new_room = self.world[room][f'to_{exit_}']
                    new_path = [*path, (new_room, exit_)]
                    if new_room == target:
                        return new_path[1:]
                    queue.append(new_path)

    def save_place(self, room: dict) -> None:
        description = room['description'].lower()
        places = ['shop', 'shrine', 'mine', 'transmogrifier', 'changer']
        for place in places:
            if place in description:
                if place == 'shrine':
                    self.places['shrine'][int(room['room_id'])] = room
                else:
                    print(f'Added a place: {place} at {int(room["room_id"])}')
                    self.places[place] = room

    def move(self, direction: str, room: int = None) -> dict:
        """Move player in the given <direction>."""
        if room is not None:
            data = {"direction": f'{direction}', "next_room_id": f"{room}"}
        else:
            data = {"direction": f'{direction}'}
        suffix = 'api/adv/move/'
        new_room = self.make_request(suffix=suffix, header=self.auth, data=data, http='post')
        self.save_place(new_room)
        print(f'\nIn room {new_room["room_id"]}. \nCurrent cooldown: {self.cooldown}')
        print(f'Items: {[item["name"] for item in self.items]}, '
              f'\nGold: {self.gold} \nStatus: {self.status_} \nEncumbrance: {self.encumbrance}')
        if new_room['items'] and not self.encumbered:
            for item in new_room['items']:
                self.take(item)
        return new_room

    def auto_play(self):
        while True:
            if self.encumbered and self.places['shop']:
                print('\nGoing to sell this treasure.', self.places['shop']['room_id'])
                path = self.move_to(int(self.places['shop']['room_id']))
                print('path', path)
                # if path:
                self.take_path(path)
                print('\nGot to the shop.')
                self.sell()

            else:
                rand_room = random.randint(0, len(self.world))
                print(f'\nGoing to room {rand_room}.')
                path = self.move_to(rand_room)
                self.take_path(path)
                print(f'\nGot to room {rand_room}.')

            if self.places['shrine']:
                for shrine in self.places['shrine']:
                    path = self.move_to(shrine)
                    print('\nGoing to pray.')
                    self.take_path(path)
                    print(f'\nGot to {shrine}.')
                    self.pray()

    def take_n_wear(self, item, wear=False):
        suffix = 'api/adv/take/'
        data = {"name": f"{item['name']}"}
        response = self.make_request(suffix=suffix, http='post', data=data, header=self.auth)
        self.items.append(item)
        self.encumbrance += item['weight']
        if wear:
            self.wear(item)
        self.status()
        return response

    def take(self, item: str) -> [dict, None]:
        """Take <item> from current room if weight limit won't be exceeded."""
        print(f'\nItem found: {item}')
        item_ = self.examine(item)
        item_weight = int(item_['weight'])
        item_type = item_['itemtype']
        # Make sure item doesn't exceed weight limit.
        if item_type == 'TREASURE':
            if self.encumbrance + item_weight < self.strength:
                self.take_n_wear(item_)
                return
        if item_type != 'TREASURE':
            if item_type == 'FOOTWEAR':
                if self.footwear and (self.encumbrance + (item_weight - self.footwear['weight']) < self.strength and
                                      int(item_['level']) > int(self.footwear['level'])):
                    self.take_n_wear(item_, wear=True)
                elif not self.footwear:
                    self.take_n_wear(item_, wear=True)
            if item_type == 'BODYWEAR':
                if self.bodywear and (self.encumbrance + (item_weight - self.bodywear['weight']) < self.strength and
                                      int(item_['level']) > int(self.bodywear['level'])):
                    self.take_n_wear(item_, wear=True)
                elif not self.bodywear:
                    self.take_n_wear(item_, wear=True)

    def wear(self, item: dict) -> [dict, None]:
        """Put on an <item>."""
        suffix = 'api/adv/wear/'
        data = {"name": item['name']}
        print(f'Seeing if {item["name"]} will fit.')
        self.status()
        item_type = None
        if 'FOOTWEAR' in item['itemtype']:
            item_type = 'footwear'
        elif 'BODYWEAR' in item['itemtype']:
            item_type = 'bodywear'
        if not item_type:
            return
        curr_item = eval(f'self.{item_type}')
        if not curr_item:
            response = self.make_request(suffix, data=data, header=self.auth, http='post')
            self.status()
            self.update_clothes(item, item_type)
            return response
        else:
            curr_item_status = self.examine(curr_item["name"])
            if int(curr_item_status['level']) < int(item['level']):
                self.remove(curr_item['name'])
                self.drop(curr_item['name'])
                response = self.make_request(suffix=suffix, data=data, header=self.auth, http='post')
                self.status()
                self.update_clothes(item, item_type)
                return response

    def update_clothes(self, item, item_type):
        if item_type == 'bodywear':
            self.bodywear = {item['name']: item}
        elif item_type == 'footwear':
            self.footwear = {item['name']: item}

    def examine(self, item: str) -> dict:
        """Examine an <item>."""
        suffix = 'api/adv/examine/'
        data = {"name": f"{item}"}
        response = self.make_request(suffix=suffix, data=data, header=self.auth, http='post')
        return response

    def pray(self) -> dict:
        suffix = 'api/adv/pray/'
        response = self.make_request(suffix=suffix, header=self.auth, http='post')
        return response

    def remove(self, item: str) -> dict:
        suffix = 'api/adv/undress/'
        data = {"name": item}
        response = self.make_request(suffix=suffix, data=data, header=self.auth, http='post')
        return response

    def drop(self, item: str) -> dict:
        suffix = 'api/adv/drop/'
        data = {"name": item}
        response = self.make_request(suffix=suffix, data=data, header=self.auth, http='post')
        return response

    def sell(self) -> None:
        suffix = 'api/adv/sell'
        while any([item['itemtype'] == 'TREASURE' for item in self.items]):
            item = self.items.popleft()
            print(f'Trying to sell {item["name"]}')
            if item['itemtype'] == 'TREASURE':
                data = {"name": item["name"]}
                self.make_request(suffix=suffix, data=data, header=self.auth, http='post')
                data = {"name": item["name"], "confirm": "yes"}
                self.make_request(suffix=suffix, data=data, header=self.auth, http='post')
                self.status()
            else:
                self.items.append(item)

    def status(self) -> dict:
        """Get the player's current status."""
        suffix = 'api/adv/status/'
        response = self.make_request(suffix=suffix, header=self.auth, http='post')
        self.speed = int(response['speed'])
        self.strength = int(response['strength'])
        self.encumbrance = int(response['encumbrance'])
        if self.encumbrance < self.strength - 1:
            self.encumbered = False
        elif self.encumbrance >= self.strength - 1:
            self.encumbered = True
        self.status_ = response['status']
        self.gold = response['gold']
        return response

    def change_name(self) -> dict:
        suffix = 'api/adv/change_name/'
        data = {"name": 'paulus'}
        response = self.make_request(suffix=suffix, data=data, header=self.auth, http='post')
        return response

    def dash(self, room, route):
        pass

    def fly(self, room):
        pass

    def warp(self):
        pass

    def carry(self):
        pass

    def receive(self):
        pass


if __name__ == '__main__':
    pass
