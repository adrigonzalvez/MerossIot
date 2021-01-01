import os

from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from meross_iot.controller.mixins.toggle import ToggleXMixin
from meross_iot.manager import MerossManager
from meross_iot.model.enums import OnlineStatus
from tests import async_get_client

if os.name == 'nt':
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
else:
    import asyncio


class TestPushNotificationHandler(AioHTTPTestCase):
    async def get_application(self):
        return web.Application()

    async def setUpAsync(self):
        # Wait some time before next test-burst
        await asyncio.sleep(10)
        self.meross_client, self.requires_logout = await async_get_client()

        # Look for a device to be used for this test
        self.meross_manager = MerossManager(http_client=self.meross_client)
        await self.meross_manager.async_init()
        devices = await self.meross_manager.async_device_discovery()
        toggle_devices = self.meross_manager.find_devices(device_class=ToggleXMixin, online_status=OnlineStatus.ONLINE)

        if len(toggle_devices) < 1:
            self.test_device = None
        else:
            self.test_device = toggle_devices[0]

    @unittest_run_loop
    async def test_dev_push_notification(self):
        if self.test_device is None:
            self.skipTest("No ToggleX device has been found to run this test on.")
            return

        # Set the toggle device to ON state
        await self.test_device.async_turn_on()

        # Create a new manager
        new_meross_client, requires_logout = await async_get_client()
        m = None
        try:
            # Retrieve the same device with another manager
            m = MerossManager(http_client=new_meross_client)
            await m.async_init()
            await m.async_device_discovery()
            devs = m.find_devices(device_uuids=(self.test_device.uuid,))
            dev = devs[0]

            e = asyncio.Event()

            # Define the coroutine for handling push notification
            async def my_coro(namespace, data, device_internal_id):
                e.set()

            dev.register_push_notification_handler_coroutine(my_coro)
            await self.test_device.async_turn_off()
            await asyncio.wait_for(e.wait(), 5.0)

        finally:
            if m is not None:
                m.close()
            if requires_logout:
                await new_meross_client.async_logout()

    async def tearDownAsync(self):
        if self.requires_logout:
            await self.meross_client.async_logout()
