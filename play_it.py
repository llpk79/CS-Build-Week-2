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
        self.encumbered = False
        self.shop = None
        self.mine = None
        self.shrines = {}

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
                print(f'Error: {response["errors"]}')

        self.then = datetime.now()  # Reset timer.
        return response

    def get_key(self) -> None:
        """Register a Player, get/set api key, set authorization dict."""
        form = {"username": "Paulus5",
                "password1": "testpassword",
                "password2": "testpassword"}
        response = self.make_request(suffix='api/registration/', data=form, http='post')
        if 'key' in response:
            key = response['key']
            self.key = key
            self.auth = {"Authorization": f"Token {self.key}",
                         "Content-Type": "application/json"}

    def initialize_player(self) -> None:
        """Create player in server database and initialize world map."""
        header = {"Authorization": f"Token {self.key}"}
        response = self.make_request(suffix='api/adv/init/', header=header, http='get')
        self.world[self.current_room] = {'meta': response,
                                         'to_n': None,
                                         'to_w': None,
                                         'to_s': None,
                                         'to_e': None}

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
        print(f'Dead-end reached. Path back to unexplored exit: {", ".join([direction for _, direction in path])}')
        for next_room in path:
            room = next_room[0]
            direction = next_room[1]
            new_room = self.move(direction, room=room)
            self.current_room = int(new_room['room_id'])

    def traverse_map(self) -> None:
        """Do a DFS to dead-end, BFS to an unexplored exit to create world map."""
        print('\nBuilding map...')
        while True:
            self.DFS_DE()
            more_to_explore = self.BFS_UE()
            if not more_to_explore:
                print('Map complete!\n')
                return
            self.take_path(more_to_explore)
            print(f'{len(self.world)} rooms found!')

    def move(self, direction: str, room: int = None) -> dict:
        """Move player in the given <direction>."""
        if room is not None:
            data = {"direction": f'{direction}', "next_room_id": f"{room}"}
        else:
            data = {"direction": f'{direction}'}
        suffix = 'api/adv/move/'
        new_room = self.make_request(suffix=suffix, header=self.auth, data=data, http='post')
        print(f'\n{" ".join(new_room["messages"])}')
        print(f'In room {new_room["room_id"]}. \nCurrent cooldown: {self.cooldown}')
        if new_room['items'] and not self.encumbered:
            for item in new_room['items']:
                self.take(item)
        return new_room

    def take(self, item: str) -> None:
        """Take <item> from current room if weight limit won't be exceeded."""
        print(f'Item found: {item}')
        # Make sure item doesn't exceed weight limit.
        curr_status = self.status()
        item_ = self.examine(item)
        item_weight = int(item_['weight'])
        if int(curr_status['strength']) - int(curr_status['encumbrance']) > item_weight:
            suffix = 'api/adv/take/'
            data = {"name": f"{item}"}
            got_item = self.make_request(suffix=suffix, http='post', data=data, header=self.auth)
            print(*got_item['messages'])
            if item_['itemtype'] != 'TREASURE':
                self.wear(item)
        else:
            self.encumbered = True

    def wear(self, item: str) -> None:
        """Put on an <item>."""
        print(f'Seeing if {item} will fit.')
        suffix = 'api/adv/wear/'
        data = {"name": item}
        curr_status = self.status()
        item_status = self.examine(item)
        item_type = None
        if 'FOOTWEAR' in item_status['itemtype']:
            item_type = 'footwear'
        elif 'BODYWEAR' in item_status['itemtype']:
            item_type = 'bodywear'
        if not item_type:
            return
        if item_type not in curr_status:
            response = self.make_request(suffix, data=data, header=self.auth, http='post')
            print(*response['messages'])
            return
        # curr_item_status = self.examine(curr_status[item_type])
        # print(f'item_status {curr_item_status}')
        # if int(curr_item_status['level']) < int(item_status['level']):
        #     self.remove()...
            #     suffix = 'api/adv/undress/'
            #     data = {"name": curr_item_status[item_type]}
            #     response = self.make_request(suffix=suffix, data=data, header=self.auth, http='post')
        #     drop it...
        #     print(*response['messages'])
        #     suffix = 'api/adv/wear/'
        #     data = {"name": item}
        #     response = self.make_request(suffix=suffix, data=data, header=self.auth, http='post')
        #     print(*response['messages'])

    def dash(self, room, route):
        pass

    def fly(self, room):
        pass

    def examine(self, item: str) -> dict:
        """Examine an <item>."""
        suffix = 'api/adv/examine/'
        data = {"name": f"{item}"}
        return self.make_request(suffix=suffix, data=data, header=self.auth, http='post')

    def pray(self):
        pass

    def remove(self, item):
        pass

    def drop(self, item):
        # update self.encumbered
        pass

    def sell(self, item):
        # update self.encumbered
        pass

    def status(self) -> dict:
        """Get the player's current status."""
        suffix = 'api/adv/status/'
        return self.make_request(suffix=suffix, header=self.auth, http='post')

    def change_name(self):
        pass


if __name__ == '__main__':
    pass
