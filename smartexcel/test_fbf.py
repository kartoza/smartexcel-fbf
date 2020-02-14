import os
import unittest

from .smart_excel import SmartExcel
from .fbf.data_model import FbfFloodData
from .fbf.definition import FBF_DEFINITION


class TestFlood(unittest.TestCase):
    def runTest(self):
        wms_base_url = os.environ.get(
            'WMS_BASE_URL',
            'http://staging.fbf.kartoza.com/geoserver/wms')
        tested_flood_event_id = os.environ.get(
            'TEST_FLOOD_EVENT_ID',
            '212'
        )
        smart_excel = SmartExcel(
            output='test_fbf.xlsx',
            definition=FBF_DEFINITION,
            data=FbfFloodData(
                wms_base_url=wms_base_url,
                flood_event_id=int(tested_flood_event_id)
            )
        )

        smart_excel.dump()

if __name__ == "__main__":
    unittest.main()
