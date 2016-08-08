from bot.lib.plugin import Plugin
from bot.lib.decorators import command

from bot.lib.helpers import parsing as p
from bot.lib.helpers import formatting as f
from bot.lib.helpers.hooks import master_only

from . import queries as q

from collections import namedtuple
from time import time

GamePlayed = namedtuple(
    'GamePlayed',
    ['id', 'author_id', 'name', 'duration', 'created_at']
)

class Stats(Plugin):

    def load(self):
        self.game_times_by_id = dict()

        now = time()

        for server in self.bot.servers:
            for member in server.members:
                if member.game:
                    game_timer = (member.game.name.lower(), now)
                    self.game_times_by_id[member.id] = game_timer

    def unload(self):
        for user_id, (game_name, start) in self.game_times_by_id.items():
            self.add_game_time(user_id, game_name, start)

    async def on_member_update(self, before, after):
        if before.game != after.game:
            self.update_game(after.id, after.game)

    '''
    Commands
    '''

    @command(
        p.string('!stats') + p.string('games') + p.bind(p.mention, 'user_id'),
        master_only
    )
    async def stats_games(self, message, user_id):
        member = message.server.get_member(str(user_id))
        if member is None:
            return

        # Flush current tracking
        self.update_game(member.id, member.game)

        with self.transaction() as trans:
            trans.execute(q.author_games, dict(
                author_id = user_id
            ))

            games = [GamePlayed(*row) for row in trans.fetchall()]
            top = [(game.name, game.duration) for game in games[:10]]

            if games:
                since = min(map(lambda g: g.created_at, games))
                since_days = int((time() - since.timestamp()) / (3600 * 24))

                response = (
                    '{} has played **{}** different games in the last **{}** days '
                    'for a total of **{}** seconds\ntop 10:\n{}'
                ).format(
                    f.mention(user_id), len(games), since_days,
                    sum(map(lambda g: g.duration, games)),
                    f.code_block(f.format_sql_rows(top))
                )
            else:
                response = '{} has not played any games yet'.format(f.mention(user_id))

            await self.send_message(
                message.channel,
                response,
                delete_after = 25
            )

    '''
    Details
    '''

    def update_game(self, user_id, new_game):
        try:
            game_name, start = self.game_times_by_id[user_id]
            self.add_game_time(user_id, game_name, start)
        except KeyError:
            pass

        if new_game:
            self.game_times_by_id[user_id] = (new_game.name.lower(), time())
        else:
            self.game_times_by_id.pop(user_id, None)

    def add_game_time(self, user_id, game_name, start):
        duration = int(time() - start)

        with self.transaction() as trans:
            trans.execute(q.add_game_time, dict(
                author_id = user_id,
                name = game_name,
                duration = duration
            ))
