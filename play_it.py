import pickle
import random
import re
import requests
from collections import deque
from cpu import CPU
from datetime import datetime
from hashlib import sha256

URL = 'https://lambda-treasure-hunt.herokuapp.com/'


class GamePlayer:
    """Plays the Lambda Treasure Hunt game.

    Once in pipenv shell:
    >>> from play_it import GamePlayer
    >>> game = GamePlayer()
    >>> game.auto_play()

    """

    def __init__(self):
        self.key = '1e255e28b47f9ce58a5d14a5a6d48ea7fa6e2599'
        self.auth = {"Authorization": f"Token {self.key}",
                     "Content-Type": "application/json"}
        self.cooldown = 0
        self.world = {}
        self.current_room = None
        self.then = datetime.now()
        self.strength = 0
        self.encumbrance = 0
        self.encumbered = False
        self.balance_ = 0
        self.status_ = []
        self.gold = 0
        self.snitches = 0
        self.bodywear = None
        self.footwear = None
        # Ensure the following variables match server state after a connection loss.
        # They are not updated with calls to self.status or initialize_player.        self.name_changed = False
        self.flight = False
        self.dash_ = False
        self.warp_ = False
        self.warped = False
        self.items_ = deque()
        self.places = {'shop': {'room_id': None},
                       'flight': {'room_id': None},
                       'dash': {'room_id': None},
                       'mine': {'room_id': None},
                       'transmog': {'room_id': None},
                       'pirate': {'room_id': None},  # Name change
                       'well': {'room_id': None},
                       'warp': {'room_id': None},
                       'warp_well': {'room_id': None}}

    def make_request(self, suffix: str, http: str, data: dict = None, header: dict = None) -> dict:
        """Make API request to game server, return dict response."""
        # Wait for cooldown period to expire.
        while (datetime.now() - self.then).seconds < self.cooldown + .1:
            pass
        if http == 'get':
            response = requests.get(URL + suffix, headers=header, data=data)
        elif http == 'post':
            response = requests.post(URL + suffix, headers=header, json=data)

        response.raise_for_status()
        response = response.json()

        # Handle response.
        if 'cooldown' in response:
            self.cooldown = float(response['cooldown'])
        if 'errors' in response:
            if response['errors']:
                print(f'\nError: {response["errors"]}')
        if 'messages' in response:
            if response['messages']:
                print(f'\n{" ".join(response["messages"])}')

        self.then = datetime.now()  # Reset timer.
        return response

    def initialize_player(self) -> None:
        """Create player in server database and initialize world map."""
        header = {"Authorization": f"Token {self.key}"}
        response = self.make_request(suffix='api/adv/init/', header=header, http='get')
        self.current_room = response['room_id']
        # If current room hasn't been saved to self.world, do that.
        if self.current_room not in self.world:
            self.world[self.current_room] = {'meta': response,
                                             'to_n': None,
                                             'to_w': None,
                                             'to_s': None,
                                             'to_e': None}
        # Save player variables locally.
        self.status()
        print(f'\nIn room {self.current_room}')
        if 'items' in response:
            for item in response['items']:
                self.take(item)
        return

    def load_map(self) -> None:
        """Load a map if one exists, otherwise, build one."""
        print('\nChecking if map saved...')
        try:
            with open('world.pickle', 'rb') as f:
                self.world = pickle.load(f)
            print('Map complete!\n')

        except FileNotFoundError:
            self._traverse_map()

    def _traverse_map(self) -> None:
        """Do a DFS to dead-end, BFS to an unexplored exit to create world map. Save map to file."""
        print('\nBuilding map...')
        while True:
            # Move to a dead-end.
            self.DFS_DE()
            # Find nearest room with an unexplored exit.
            more_to_explore = self.BFS_UE()
            # If none exist, we have traversed to every room.
            if not more_to_explore:
                print('Map complete!\n')
                # Save the map.
                with open('world.pickle', 'wb') as f:
                    pickle.dump(self.world, f)
                return
            # Move along path to room with an unexplored exit.
            self.take_path(more_to_explore)
            print(f'{len(self.world)} rooms found!')

    def get_exits(self, room: int) -> list:
        """Return list of all exits from <room>."""
        return self.world[room]['meta']['exits']

    def BFS_UE(self) -> list:
        """Create path to nearest unexplored exit by BFS."""
        # Initialize variable.
        visited = set()
        queue = deque()
        path = (self.current_room, '')
        queue.append([path])

        while queue:
            # Get the last room from a path in the queue.
            path = queue.popleft()
            room = path[-1][0]
            # Move on if we've already been in this room.
            if room not in visited:
                visited.add(room)
                exits = self.get_exits(room)
                # Stop if any exit is unexplored.
                if any([self.world[room][f'to_{exit_}'] is None for exit_ in exits]):
                    return path[1:]  # Omit the room we're already in.
                # Add a new path to each exit to the queue.
                for exit_ in exits:
                    new_room = self.world[room][f'to_{exit_}']
                    new_path = [*path, (new_room, exit_)]
                    queue.append(new_path)

    def DFS_DE(self) -> None:
        """Take first available unexplored exit until current room contains no unexplored exits."""
        rev_dir = {'n': 's', 'w': 'e', 's': 'n', 'e': 'w'}
        while True:
            exits = self.get_exits(self.current_room)

            # If we've explored all exits, return.
            if all([self.world[self.current_room][f'to_{exit_}'] is not None for exit_ in exits]):
                return

            # Get all unexplored exits.
            open_exits = [d for d in exits if self.world[self.current_room][f'to_{d}'] is None]

            # Take the first open path.
            open_exit = open_exits[0]
            fly = True
            if self.world[self.current_room]['meta']['terrain'] == "CAVE":
                fly = False
            new_room = self.move(open_exit, fly=fly)
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

    def find_path(self, target: int) -> list:
        """Create a path to a <target> room with BFS."""
        if self.current_room == target:
            return []
        visited = set()
        path = [(self.current_room, '')]
        queue = deque()
        queue.append(path)
        while queue:
            # Get the last room in the next path from queue.
            path = queue.popleft()
            room = path[-1][0]
            # Move along if we've seen this room before.
            if room not in visited:
                visited.add(room)
                exits = self.get_exits(room)
                for exit_ in exits:
                    # Make a new path to each exit.
                    new_room = self.world[room][f'to_{exit_}']
                    new_path = [*path, (new_room, exit_)]
                    # Stop when finding our target room.
                    if new_room == target:
                        return new_path[1:]
                    queue.append(new_path)

    def take_path(self, path: list) -> None:
        """Move along the <path>. Fly if able."""
        for next_room in path:
            room = next_room[0]
            direction = next_room[1]
            # Don't fly in caves!
            if self.flight and self.world[room]['meta']['terrain'] != 'CAVE':
                new_room = self.move(direction, room=room, fly=True)
            else:
                new_room = self.move(direction, room=room)
            self.current_room = int(new_room['room_id'])

    def save_place(self, room: dict) -> None:
        """Save a room to the places dict."""
        title = room['title'].lower()
        for place in self.places:
            if place in title:
                print(f'Added a place: {place} at {int(room["room_id"])}')
                self.places[place] = room

    def move(self, direction: str, room: int = None, fly: bool = False) -> dict:
        """Move player in the given <direction>. Fly if able."""
        # Get cooldown bonus of being a wise explorer by supplying a <room>.
        if room is not None:
            data = {"direction": f'{direction}', "next_room_id": f"{room}"}
        else:
            data = {"direction": f'{direction}'}
        suffix = 'api/adv/move/'
        if fly:
            suffix = 'api/adv/fly/'
        new_room = self.make_request(suffix=suffix, header=self.auth, data=data, http='post')
        self.save_place(new_room)
        # Print status info.
        print(f'\nIn room {new_room["room_id"]}. \nCurrent cooldown: {self.cooldown}')
        print(f'Items: {[item["name"] for item in self.items_]}, '
              f'\nPlaces: {[(x, y["room_id"]) for x, y in self.places.items() if y]}, '
              f'\nGold: {self.gold}, Lambda Coins: {self.balance_}, Snitches: {self.snitches}'
              f'\nEncumbrance: {self.encumbrance}, Strength: {self.strength}')
        # Pick up items if we can.
        if new_room['items'] and not self.encumbered:
            for item in new_room['items']:
                self.take(item)
        return new_room

    def auto_play(self) -> None:
        """Helper function for starting game."""
        self.load_map()
        self.initialize_player()
        self.play()

    def sell_things(self):
        """Move to the shop and sell all the treasure."""
        print('\nGoing to sell this treasure.')
        path = self.find_path(int(self.places['shop']['room_id']))
        if self.dash_:
            self.dash(path)
        else:
            self.take_path(path)
        print('\nGot to the shop.')
        self.sell()
        self.status()

    def rand_room(self) -> None:
        """Go to a random room."""
        start, end = 0, 499
        if self.warped:
            start, end = 500, 999
        rand_room = random.randint(start, end)
        print(f'\nGoing to room {rand_room}.')
        path = self.find_path(rand_room)
        self.take_path(path)
        print(f'\nGot to room {rand_room}.')

    def name_change(self) -> None:
        """Go to the name changing pirate and get your true name."""
        print('\nGoing to pirate.')
        path = self.find_path(int(self.places['pirate']['room_id']))
        self.take_path(path)
        self.change_name()
        self.name_changed = True
        self.status()

    def to_dash(self) -> None:
        """Go to the dash shrine and pray."""
        print('\nGoing to dash')
        path = self.find_path(int(self.places['dash']['room_id']))
        self.take_path(path)
        print(f'\nGot to dash.')
        self.pray()
        self.dash_ = True
        self.status()

    def to_flight(self) -> None:
        """Go to the flight shrine and pray."""
        print('\nGoing to flight')
        path = self.find_path(int(self.places['flight']['room_id']))
        self.take_path(path)
        print(f'\nGot to flight.')
        self.pray()
        self.flight = True
        self.status()

    def to_warp(self) -> None:
        """Go to the warp shrine and pray."""
        print('\nGoing to warp...')
        path = self.find_path(self.places['warp']['room_id'])
        self.dash(path)
        print('Got to warp shrine.')
        self.pray()
        self.warp_ = True
        self.status()

    def dimensional_traveler(self) -> None:
        """Warp to alternate dimension, find well, decode clue, go grab snitch, warp back to reality."""
        print('Warping...')
        self.warp()
        # Make sure self.current_room is correct.
        self.initialize_player()
        print('Going to well...')
        path = self.find_path(self.places['warp_well']['room_id'])
        self.dash(path)
        print('Wishing...')
        self.wish()
        print('Going to snitch...')
        path = self.find_path(int(self.places['mine']['room_id']))
        self.dash(path)
        self.take('golden snitch')
        self.warp()
        self.initialize_player()

    def coin_dash(self) -> None:
        """Dash to the well, then the mine, mine a coin."""
        print('Going to wishing well...')
        path = self.find_path(int(self.places['well']['room_id']))
        self.dash(path)
        print('Got to the wishing well.')
        self.wish()
        print('Going to the mine...')
        path = self.find_path(int(self.places['mine']['room_id']))
        self.dash(path)
        print('Got to the mine.')
        self.proof()

    def play(self) -> None:
        """Go to random rooms to find treasure, sell when encumbered, and pray if able, mine coins, find snitches.

         Do it forever.
         """
        while True:
            # Go to a random rooms to collect treasure until you can carry no more.
            if not self.encumbered:
                self.rand_room()
            # Change name if not already done.
            if self.places['pirate']['room_id'] and not self.name_changed and self.gold >= 1000:
                self.name_change()
            # Pray at the dash shrine once.
            if self.places['dash']['room_id'] and self.name_changed and not self.dash_:
                self.to_dash()
            # Pray at the flight shrine once.
            if self.places['flight']['room_id'] and self.name_changed and not self.flight:
                self.to_flight()
            # Pray at the warp shrine once.
            if self.places['warp']['room_id'] and self.name_changed and not self.warp:
                self.to_warp()
            # Go get a golden snitch.
            if self.encumbered and self.warp_:
                self.dimensional_traveler()
            # Mine lambda a coin.
            if self.encumbered and self.places['well']['room_id'] and self.name_changed:
                self.coin_dash()
            # Sell treasure.
            if self.encumbered and self.places['shop']['room_id']:
                self.sell_things()

    def take(self, item: str) -> None:
        """Take <item> from current room if weight limit won't be exceeded."""
        print(f'\nYou found {item}')
        # Get item dict.
        item_ = self.examine(item)
        # Only get snitches in alternate dimension.
        if self.warped:
            suffix = 'api/adv/take/'
            data = {"name": "golden snitch"}
            self.make_request(suffix=suffix, data=data, header=self.auth, http='post')
            return
        if not self.warped:
            # Get item attributes from dict.
            item_weight = int(item_['weight'])
            item_type = item_['itemtype']
            if item_type == 'TREASURE':
                # Make sure item doesn't exceed weight limit.
                if self.encumbrance + item_weight < self.strength:
                    self.take_n_wear(item_)
                    return
            elif item_type != 'TREASURE':
                if item_type == 'FOOTWEAR':
                    # Make sure item doesn't exceed weight limit.
                    if self.footwear and (self.encumbrance + (item_weight - self.footwear['weight']) < self.strength):
                        self.take_n_wear(item_, wear=True)
                    elif not self.footwear:
                        self.take_n_wear(item_, wear=True)
                if item_type == 'BODYWEAR':
                    # Make sure item doesn't exceed weight limit.
                    if self.bodywear and (self.encumbrance + (item_weight - self.bodywear['weight']) < self.strength):
                        self.take_n_wear(item_, wear=True)
                    elif not self.bodywear:
                        self.take_n_wear(item_, wear=True)

    def take_n_wear(self, item: dict, wear: bool = False) -> dict:
        """Take item, call wear() if item is wearable, add treasure to inventory."""
        suffix = 'api/adv/take/'
        data = {"name": f"{item['name']}"}
        response = self.make_request(suffix=suffix, http='post', data=data, header=self.auth)
        self.encumbrance += item['weight']
        if wear:
            self.wear(item)
        else:
            self.items_.append(item)
        self.status()
        return response

    def wear(self, item: dict) -> dict:
        """Put on an <item> if it makes sense to."""
        print(f'Seeing if {item["name"]} will fit.')
        if 'FOOTWEAR' in item['itemtype']:
            curr_item = self.footwear
        elif 'BODYWEAR' in item['itemtype']:
            curr_item = self.bodywear
        # Check if we're already wearing something.
        if curr_item is None:
            suffix = 'api/adv/wear/'
            data = {"name": item['name']}
            response = self.make_request(suffix, data=data, header=self.auth, http='post')
            self.update_clothes(item)
            return response
        else:
            # Check if the new item is better.
            if int(curr_item['level']) < int(item['level']):
                # Remove and drop old item, wear new item, and update attributes.
                self.remove(curr_item['name'])
                self.drop(curr_item['name'])
                suffix = 'api/adv/wear/'
                data = {"name": item['name']}
                response = self.make_request(suffix=suffix, data=data, header=self.auth, http='post')
                self.update_clothes(item)
                return response
            self.drop(item['name'])

    def update_clothes(self, item: dict) -> None:
        """Update instance attributes."""
        if item['itemtype'] == 'BODYWEAR':
            self.bodywear = item
        elif item['itemtype'] == 'FOOTWEAR':
            self.footwear = item

    def examine(self, item: str) -> dict:
        """Examine an <item>."""
        suffix = 'api/adv/examine/'
        data = {"name": f"{item}"}
        response = self.make_request(suffix=suffix, data=data, header=self.auth, http='post')
        return response

    def pray(self) -> dict:
        """Pray at a shrine."""
        suffix = 'api/adv/pray/'
        response = self.make_request(suffix=suffix, header=self.auth, http='post')
        return response

    def remove(self, item: str) -> dict:
        """Remove the <item>."""
        suffix = 'api/adv/undress/'
        data = {"name": item}
        response = self.make_request(suffix=suffix, data=data, header=self.auth, http='post')
        return response

    def drop(self, item: str) -> dict:
        """Drop the <item>."""
        suffix = 'api/adv/drop/'
        data = {"name": item}
        response = self.make_request(suffix=suffix, data=data, header=self.auth, http='post')
        # Remove item from inventory.
        while any([item_['name'] == item for item_ in self.items_]):
            thing = self.items_.popleft()
            if thing['name'] == item:
                continue
            else:
                self.items_.append(thing)
        return response

    def sell(self) -> None:
        """Sell all of the treasure items, keep the rest."""
        suffix = 'api/adv/sell'
        while any([item['itemtype'] == 'TREASURE' for item in self.items_]):
            item = self.items_.popleft()
            if item['itemtype'] == 'TREASURE':
                print(f'Selling {item["name"]}')
                data = {"name": item["name"]}
                self.make_request(suffix=suffix, data=data, header=self.auth, http='post')
                data = {"name": item["name"], "confirm": "yes"}
                self.make_request(suffix=suffix, data=data, header=self.auth, http='post')
            else:
                self.items_.append(item)
        self.status()

    def status(self) -> dict:
        """Get the player's current status, set instance variables."""
        suffix = 'api/adv/status/'
        response = self.make_request(suffix=suffix, header=self.auth, http='post')
        # Update relevant instance variables.
        self.strength = int(response['strength'])
        self.encumbrance = int(response['encumbrance'])
        self.status_ = response['status']
        self.gold = response['gold']
        self.snitches = response['snitches']
        # Ensure timely sale of items by lowering sale threshold as item weight increases.
        # We won't wander forever looking for that one tiny treasure we need to trigger sale.
        if self.items_:
            heaviest_item = max([item['weight'] for item in self.items_])
        else:
            heaviest_item = 1
        if self.encumbrance < self.strength - heaviest_item:
            self.encumbered = False
        elif self.encumbrance >= self.strength - heaviest_item:
            self.encumbered = True
        return response

    def change_name(self) -> dict:
        """Ask the name changing pirate to change your name."""
        suffix = 'api/adv/change_name/'
        data = {"name": "paulus", "confirm": "aye"}
        response = self.make_request(suffix=suffix, data=data, header=self.auth, http='post')
        return response

    def dash(self, path: list) -> None:
        """Use the 'dash' ability to travel straight sections in one move.

        Make lists of rooms until direction changes, submit dash request, then repeat.
        """
        if not path:
            return
        suffix = 'api/adv/dash/'
        # Path given in current -> target, reverse so we can pop current.
        path = list(reversed(path))
        # Initialize variables.
        start = path.pop()
        start_room, start_direction = start[0], start[1]
        rooms = [start_room]  # Our current room.
        while path:
            # Get next room on path.
            new = path.pop()
            new_room = new[0]
            new_direction = new[1]
            # If we're still going the same way, append and carry on.
            if new_direction == start_direction:
                rooms.append(new_room)
            # Otherwise, create dash request.
            else:
                data = {"direction": f"{start_direction}",
                        "num_rooms": f"{len(rooms)}",
                        "next_room_ids": f"{','.join(map(str, rooms))}"}
                self.make_request(suffix=suffix, data=data, header=self.auth, http='post')
                start_direction = new_direction
                rooms = [new_room]
        # Handle any remaining rooms.
        data = {"direction": f"{start_direction}",
                "num_rooms": f"{len(rooms)}",
                "next_room_ids": f"{','.join(map(str, rooms))}"}
        self.make_request(suffix=suffix, data=data, header=self.auth, http='post')
        self.current_room = rooms[-1]
        self.status()

    def wish(self) -> None:
        """Wish at a well to get a clue. Decode clue."""
        response = self.examine('WELL')
        code = response['description'].split('\n')
        # Save code to disc.
        with open('clue.ls8', 'w') as f:
            for line in code[2:]:
                f.write(line)
                f.write('\n')
        # Run file on CPU.
        cpu = CPU()
        cpu.load()
        cpu.run()
        next_string = cpu.next_room  # CPU modified to output strings to next_room attribute.
        # Extract digits from string.
        room = re.search(r'\d+', next_string)
        next_room = int(room.group(0))
        print(f'\nMine found: {next_room}')
        # Update room id.
        self.places['mine']['room_id'] = next_room

    def warp(self) -> dict:
        """Warp to alternate dimension."""
        suffix = 'api/adv/warp/'
        response = self.make_request(suffix=suffix, header=self.auth, http='post')
        self.warped = not self.warped
        return response

    def transmogrify(self, item: str) -> dict:
        """Use machine to turn treasure into clothing."""
        suffix = 'api/adv/transmogrify/'
        data = {"name": item}
        response = self.make_request(suffix=suffix, data=data, header=self.auth, http='post')
        return response

    def proof(self) -> None:
        """Retrieve last proof from mine."""
        suffix = 'api/bc/last_proof/'
        auth = {'Authorization': f"Token {self.key}"}
        response = self.make_request(suffix=suffix, header=auth, http='get')
        last_proof = response['proof']
        difficulty = response['difficulty']
        self.new_proof(last_proof, difficulty)

    def new_proof(self, last_proof: int, difficulty: int) -> None:
        """Generate new proof to mine new block."""
        x = 0
        print(f'Finding proof...\nlast_proof: {last_proof}, difficulty: {difficulty}')
        while True:
            string = (str(last_proof) + str(x)).encode()
            hash_ = sha256(string).hexdigest()
            if hash_[:difficulty] == '0' * difficulty:
                print(f'Submitting proof: {x}')
                self.mine(x)
                break
            x += 1

    def mine(self, new_proof: int) -> dict:
        """Submit <new_proof> to mine a new lambda coin."""
        suffix = 'api/bc/mine/'
        data = {"proof": new_proof}
        response = self.make_request(suffix=suffix, data=data, header=self.auth, http='post')
        self.balance()
        return response

    def balance(self) -> None:
        """Get and update lambda coin balance."""
        suffix = 'api/bc/get_balance/'
        auth = {"Authorization": f"Token {self.key}"}
        response = self.make_request(suffix=suffix, header=auth, http='get')
        message = response['messages']
        balance = re.search(r'\d+', *message)
        self.balance_ = int(balance.group(0))


if __name__ == '__main__':
    pass
