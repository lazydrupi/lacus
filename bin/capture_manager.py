#!/usr/bin/env python3

import asyncio
import logging
import signal

from asyncio import Task
from typing import Set

from redis import Redis

from lacus.default import AbstractManager, get_config, get_socket_path
from lacus.lacus import Lacus

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO)


class CaptureManager(AbstractManager):

    def __init__(self, loglevel: int=logging.INFO):
        super().__init__(loglevel)
        self.script_name = 'capture_manager'
        self.captures: Set[Task] = set()
        self.redis: Redis = Redis(unix_socket_path=get_socket_path('cache'))
        self.lacus = Lacus()

    async def _capture(self):
        self.set_running()
        await self.lacus.core.consume_queue()
        self.unset_running()

    async def _to_run_forever_async(self):
        await super()._to_run_forever_async()
        capture = asyncio.create_task(self._capture())
        capture.add_done_callback(self.captures.discard)
        self.captures.add(capture)
        while len(self.captures) >= get_config('generic', 'concurrent_captures'):
            await asyncio.sleep(1)

    async def _wait_to_finish(self):
        while self.captures:
            self.logger.info(f'Waiting for {len(self.captures)} capture(s) to finish...')
            await asyncio.sleep(5)
        self.logger.info('No more captures')


def main():
    p = CaptureManager()

    loop = asyncio.new_event_loop()
    loop.add_signal_handler(signal.SIGTERM, lambda: loop.create_task(p.stop_async()))

    try:
        loop.run_until_complete(p.run_async(sleep_in_sec=1))
    finally:
        loop.close()


if __name__ == '__main__':
    main()
