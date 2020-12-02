import os
from urllib.parse import urlencode
from collections import namedtuple
import shutil
import requests
import psycopg2

try:
    import plpy
except:
    pass


def namedtuplefetchall(cursor):
    "Return all rows from a cursor as a namedtuple"
    desc = cursor.description
    nt_result = namedtuple('Result', [col[0] for col in desc])
    return [nt_result(*row) for row in cursor.fetchall()]


class FbfFloodData():
    trigger_status = [
        {'id': 0, 'status': 'No activation', 'color': '#72CA7A'},
        {'id': 1, 'status': 'Pre-activation', 'color': '#D39858'},
        {'id': 2, 'status': 'Activation', 'color': '#CA6060'},
        {'id': 3, 'status': 'Stop', 'color': '#FF0000'}
    ]

    def __init__(self, flood_event_id, pl_python_env=None, wms_base_url=None):
        self.flood_event_id = flood_event_id
        self.wms_base_url = wms_base_url
        if not self.wms_base_url:
            self.wms_base_url = 'http://staging.fbf.kartoza.com/' \
                                'geoserver/kartoza/wms'

        if pl_python_env:
            self.pl_python_env = pl_python_env
        else:
            self.connection = psycopg2.connect(
                user=os.environ['DB_USER'],
                password=os.environ['DB_PASSWORD'],
                host=os.environ['DB_HOST'],
                port=os.environ['DB_PORT'],
                database=os.environ['DB_DATABASE'])
            self.pl_python_env = False

        countries_summary = self.get_countries(flood_event_id)

        self.results = {
            'flood': self.get_flood(flood_event_id),
            'countries': countries_summary
        }

    def execute_query(self, query):
        if self.pl_python_env:
            res = plpy.execute(query)
            try:
                fields = list(res[0].keys())

                def_meta_res = namedtuple('Result', ', '.join(fields))

                results = [
                    def_meta_res(*list(res[index].values()))
                    for index in range(0, len(res))
                ]
            except IndexError:
                results = []
            return results

        else:
            with self.connection.cursor() as cursor:
                cursor.execute(query)
                results = namedtuplefetchall(cursor)

        return results

    def get_countries(self, flood_event_id):

        query = f"""
            select
                event_id,
                country.name as country_name,
                country_id as country_code,
                sum(vulnerability_score) as vulnerability_score,
                sum(total_buildings) as total_buildings,
                sum(flooded_buildings) as flooded_buildings,
                sum(activation_state) as activation_state,
                sum(total_roads) as total_roads,
                sum(flooded_roads) as flooded_roads,
                sum(total_population) as total_population,
                sum(flooded_population) as flooded_population
            from
                (select
                flood_event_id as event_id,
                country_id,
                total_vulnerability_score as vulnerability_score,
                building_count as total_buildings,
                flooded_building_count as flooded_buildings,
                trigger_status as activation_state,
                null::int as total_roads,
                null::int as flooded_roads,
                null::int as total_population,
                null::int as flooded_population
            from mv_flood_event_country_summary
            union
            select
                flood_event_id as event_id,
                country_id,
                null::int as vulnerability_score,
                null::int as total_buildings,
                null::int as flooded_buildings,
                null::int as activation_state,
                road_count as total_roads,
                flooded_road_count as flooded_roads,
                null::int as total_population,
                null::int as flooded_population
            from mv_flood_event_road_country_summary
            union
            select
                flood_event_id as event_id,
                country_id,
                null::int as vulnerability_score,
                null::int as total_buildings,
                null::int as flooded_buildings,
                null::int as activation_state,
                null::int as total_roads,
                null::int as flooded_roads,
                population_count as total_population,
                flooded_population_count as flooded_population
            from mv_flood_event_population_country_summary) impact
            join country on impact.country_id = country.country_code
            where impact.event_id = {flood_event_id}
            group by event_id, country_id, name
            order by name asc
        """

        return self.execute_query(query)

    def get_districts(self, flood_event_id, country_code):

        query = f"""
            select
                event_id,
                district.name as district_name,
                district_id as district_code,
                sum(vulnerability_score) as vulnerability_score,
                sum(total_buildings) as total_buildings,
                sum(flooded_buildings) as flooded_buildings,
                sum(activation_state) as activation_state,
                sum(total_roads) as total_roads,
                sum(flooded_roads) as flooded_roads,
                sum(total_population) as total_population,
                sum(flooded_population) as flooded_population
            from
                (select
                flood_event_id as event_id,
                district_id,
                total_vulnerability_score as vulnerability_score,
                building_count as total_buildings,
                flooded_building_count as flooded_buildings,
                trigger_status as activation_state,
                null::int as total_roads,
                null::int as flooded_roads,
                null::int as total_population,
                null::int as flooded_population
            from mv_flood_event_district_summary
            union
            select
                flood_event_id as event_id,
                district_id,
                null::int as vulnerability_score,
                null::int as total_buildings,
                null::int as flooded_buildings,
                null::int as activation_state,
                road_count as total_roads,
                flooded_road_count as flooded_roads,
                null::int as total_population,
                null::int as flooded_population
            from mv_flood_event_road_district_summary
            union
            select
                flood_event_id as event_id,
                district_id,
                null::int as vulnerability_score,
                null::int as total_buildings,
                null::int as flooded_buildings,
                null::int as activation_state,
                null::int as total_roads,
                null::int as flooded_roads,
                population_count as total_population,
                flooded_population_count as flooded_population
            from mv_flood_event_population_district_summary) impact
            join district on impact.district_id = district.dc_code
            where 
                impact.event_id = {flood_event_id}
                and district.country_code = {country_code}
            group by event_id, district_id, name
            order by name asc
        """

        return self.execute_query(query)

    def get_subdistricts(self, flood_event_id, district_code):

        query = f"""
            select
                event_id,
                sub_district.name as sub_district_name,
                sub_district_id as sub_district_code,
                sum(vulnerability_score) as vulnerability_score,
                sum(total_buildings) as total_buildings,
                sum(flooded_buildings) as flooded_buildings,
                sum(activation_state) as activation_state,
                sum(total_roads) as total_roads,
                sum(flooded_roads) as flooded_roads,
                sum(total_population) as total_population,
                sum(flooded_population) as flooded_population
            from
                (select
                flood_event_id as event_id,
                sub_district_id,
                total_vulnerability_score as vulnerability_score,
                building_count as total_buildings,
                flooded_building_count as flooded_buildings,
                trigger_status as activation_state,
                null::int as total_roads,
                null::int as flooded_roads,
                null::int as total_population,
                null::int as flooded_population
            from mv_flood_event_sub_district_summary
            union
            select
                flood_event_id as event_id,
                sub_district_id,
                null::int as vulnerability_score,
                null::int as total_buildings,
                null::int as flooded_buildings,
                null::int as activation_state,
                road_count as total_roads,
                flooded_road_count as flooded_roads,
                null::int as total_population,
                null::int as flooded_population
            from mv_flood_event_road_sub_district_summary
            union
            select
                flood_event_id as event_id,
                sub_district_id,
                null::int as vulnerability_score,
                null::int as total_buildings,
                null::int as flooded_buildings,
                null::int as activation_state,
                null::int as total_roads,
                null::int as flooded_roads,
                population_count as total_population,
                flooded_population_count as flooded_population
            from mv_flood_event_population_sub_district_summary) impact
            join sub_district on impact.sub_district_id = sub_district.sub_dc_code
            where 
                impact.event_id = {flood_event_id}
                and sub_district.dc_code = {district_code}
            group by event_id, sub_district_id, name
            order by name asc
        """

        return self.execute_query(query)

    def get_villages(self, flood_event_id, sub_district_code):
        query = f"""
            select
                event_id,
                village.name as village_name,
                village_id as village_code,
                sum(vulnerability_score) as vulnerability_score,
                sum(total_buildings) as total_buildings,
                sum(flooded_buildings) as flooded_buildings,
                sum(activation_state) as activation_state,
                sum(total_roads) as total_roads,
                sum(flooded_roads) as flooded_roads,
                sum(total_population) as total_population,
                sum(flooded_population) as flooded_population
            from
                (select
                flood_event_id as event_id,
                village_id,
                total_vulnerability_score as vulnerability_score,
                building_count as total_buildings,
                flooded_building_count as flooded_buildings,
                trigger_status as activation_state,
                null::int as total_roads,
                null::int as flooded_roads,
                null::int as total_population,
                null::int as flooded_population
            from mv_flood_event_village_summary
            union
            select
                flood_event_id as event_id,
                village_id,
                null::int as vulnerability_score,
                null::int as total_buildings,
                null::int as flooded_buildings,
                null::int as activation_state,
                road_count as total_roads,
                flooded_road_count as flooded_roads,
                null::int as total_population,
                null::int as flooded_population
            from mv_flood_event_road_village_summary
            union
            select
                flood_event_id as event_id,
                village_id,
                null::int as vulnerability_score,
                null::int as total_buildings,
                null::int as flooded_buildings,
                null::int as activation_state,
                null::int as total_roads,
                null::int as flooded_roads,
                population_count as total_population,
                flooded_population_count as flooded_population
            from mv_flood_event_population_village_summary) impact
            join village on impact.village_id = village.village_code
            where 
                impact.event_id = {flood_event_id}
                and village.sub_dc_code = {sub_district_code}
            group by event_id, village_id, name
            order by name asc
        """

        return self.execute_query(query)

    def get_flood(self, flood_event_id):
        query = """
            SELECT
                *
            FROM
                hazard_event fe
            WHERE
                fe.id = {flood_event_id}
        """.format(
            flood_event_id=flood_event_id
        )

        return self.execute_query(query)

    def get_flood_extent(self, flood_event_id):
        query = """
            SELECT *
            FROM vw_hazard_event_extent fee
            WHERE fee.id = {flood_event_id}
        """.format(
            flood_event_id=flood_event_id
        )
        return self.execute_query(query)

    def get_area_extent(self, params, area_code):
        query = """
            SELECT x_min, y_min, x_max, y_max
            FROM vw_{table}_extent
            WHERE id_code = '{area_code}'
        """.format(
            table=params['table'],
            foreign_key=params['foreign_key'],
            area_code=area_code
        )
        return self.execute_query(query)

    def get_payload_districts(self, instance, foreign_key):
        country_code = int(getattr(instance, foreign_key))
        return self.get_districts(self.flood_event_id, country_code)

    def get_payload_subdistricts(self, instance, foreign_key):
        district_code = int(getattr(instance, foreign_key))
        return self.get_subdistricts(self.flood_event_id, district_code)

    def get_payload_villages(self, instance, foreign_key):
        sub_district_code = int(getattr(instance, foreign_key))
        return self.get_villages(self.flood_event_id, sub_district_code)

    def get_payload_subdistrict_detail(self, instance, foreign_key):
        return [instance]

    def get_payload_village_detail(self, instance, foreign_key):
        return [instance]

    def get_sheet_name_for_flood_summary(self, kwargs={}):
        return f"Impact Summary"

    def get_sheet_name_for_district_summary(self, instance, kwargs={}):
        name = f"Country {instance.country_name} Summary"
        return name[0:30]

    def get_sheet_name_for_subdistrict_summary(self, instance, kwargs={}):
        name = f"District {instance.district_name} Summary"
        return name[0:30]

    def get_sheet_name_for_subdistrict_detail(self, instance, kwargs={}):
        name = f"Sub District {instance.sub_district_name} Summary"
        return name[0:30]

    def get_sheet_name_for_village_summary(self, instance, kwargs={}):
        name = f"Sub district {instance.sub_district_name} Summary"
        return name[0:30]

    def get_sheet_name_for_village_detail(self, instance, kwargs={}):
        name = f"Village {instance.village_name} Summary"
        return name[0:30]

    def write_flood_title(self, instance, kwargs={}):
        return f"Impact {instance.id}"

    def write_flood_acquisition_date(self, instance, kwargs={}):
        try:
            if isinstance(instance.acquisition_date, str):
                return instance.acquisition_date
            else:
                return instance.acquisition_date.strftime('%Y-%m-%d')
        except Exception:
            return None

    def write_flood_forecast_date(self, instance, kwargs={}):
        try:
            if isinstance(instance.forecast_date, str):
                return instance.forecast_date
            else:
                return instance.forecast_date.strftime('%Y-%m-%d')
        except Exception:
            return None

    def write_flood_source(self, instance, kwargs={}):
        return instance.source

    def write_flood_notes(self, instance, kwargs={}):
        return instance.notes

    def write_flood_link(self, instance, kwargs={}):
        return instance.link

    def write_flood_trigger_status(self, instance, kwargs={}):
        for status in self.trigger_status:
            if status['id'] == instance.trigger_status:
                return status['status']
        return 'No action'

    def get_format_for_trigger_status(self, instance):
        cell_format = {
            'bold': True,
            'align': 'center',
            'bg_color': ''
        }

        for status in self.trigger_status:
            if status['id'] == instance.trigger_status:
                cell_format['bg_color'] = status['color']
                return cell_format

        cell_format['bg_color'] = '#ddddd'
        return cell_format

    def write_country_name(self, instance, kwargs={}):
        return instance.country_name

    def write_district_name(self, instance, kwargs={}):
        return instance.district_name

    def write_district_code(self, instance, kwargs={}):
        return instance.district_code

    def write_sub_district_name(self, instance, kwargs={}):
        return instance.sub_district_name

    def write_sub_district_id(self, instance, kwargs={}):
        return instance.sub_district_code

    def write_village_name(self, instance, kwargs={}):
        return instance.village_name

    def write_village_id(self, instance, kwargs={}):
        # village_id : 3201160018.0
        # cast to int to remove the decimal
        # then to str because 3,201,160,018 is bigger than 2,147,483,647
        return str(int(instance.village_code))

    def write_total_buildings(self, instance, kwargs={}):
        return instance.total_buildings

    def write_flooded_buildings(self, instance, kwargs={}):
        return instance.flooded_buildings

    def write_not_flooded_buildings(self, instance, kwargs={}):
        try:
            return instance.total_buildings - instance.flooded_buildings
        except Exception:
            return 0

    def write_total_roads(self, instance, kwargs={}):
        try:
            total_road = instance.total_roads
        except Exception:
            total_road = 0
        return total_road

    def write_flooded_roads(self, instance, kwargs={}):
        try:
            total_road = instance.flooded_roads
        except Exception:
            total_road = 0
        return total_road

    def write_not_flooded_roads(self, instance, kwargs={}):
        try:
            return instance.total_roads - instance.flooded_roads
        except Exception:
            return 0

    def write_total_population(self, instance, kwargs={}):
        try:
            total_population = instance.total_population
        except Exception:
            total_population = 0
        return total_population

    def write_flooded_population(self, instance, kwargs={}):
        try:
            flooded_population = instance.flooded_population
        except Exception:
            flooded_population = 0
        return flooded_population

    def write_not_flooded_population(self, instance, kwargs={}):
        try:
            return instance.total_population - instance.flooded_population
        except Exception:
            return 0

    def write_vulnerability_total_score(self, instance, kwargs={}):
        return instance[kwargs['index']]['vulnerability_total_score']

    def write_building_count(self, instance, kwargs={}):
        return instance.building_count

    def write_flooded_building_count(self, instance, kwargs={}):
        return instance.flooded_building_count

    def write_residential_building_count(self, instance, kwargs={}):
        return instance.residential_building_count

    def write_residential_flooded_building_count(self, instance, kwargs={}):
        return instance.residential_flooded_building_count

    def write_clinic_dr_building_count(self, instance, kwargs={}):
        return instance.clinic_dr_building_count

    def write_clinic_dr_flooded_building_count(self, instance, kwargs={}):
        return instance.clinic_dr_flooded_building_count

    def get_text_for_main_sheet_title(self):
        return 'FbF Impact Summary Report'

    def get_text_for_main_sheet_sub_title(self):
        return 'Overview Map'

    def get_text_for_country_sheet_title(self, instance):
        return f'Country: {instance.country_name}'

    def get_text_for_district_sheet_title(self, instance):
        return f'District: {instance.district_name}'

    def get_text_for_sub_district_sheet_title(self, instance):
        return f'Sub-district: {instance.sub_district_name}'

    def get_text_for_village_sheet_title(self, instance):
        return f'Village: {instance.village_name}'

    def get_image_partner_logos(self, size):
        return path_to_image('partner_logos_medium.png')

    def get_image_fba_logo(self, size):
        return path_to_image('fba-inasafe.png')

    def get_image_kartoza_logo(self, size):
        return path_to_image('kartoza2.png')

    def map_ratio_calculations(self, extent, image_ratio):
        # bbox and size has to be proportionals

        # substract x_max and x_min => width
        # substract y_max and y_min => height

        # with width and height, get the ratio

        # compare ratio (e.g: 7/3) with `size` ratio (700x400)
        # if bigger, scale the height
        # y_max * image_ratio / extent_radio
        # if smaller, scale the width

        extent_width, extent_height = extent.x_max - extent.x_min, extent.y_max - extent.y_min
        # create mutable extent to store the new extent value
        Extent = namedtuple('Extent', 'x_min y_min x_max y_max')
        extent_ratio = extent_width / extent_height
        if extent_ratio > image_ratio:
            # width of the bbox is bigger. accommodate more height
            new_extent_height = extent_ratio / image_ratio * extent_height
            half_difference = (new_extent_height - extent_height) / 2
            # Add buffer of 1/10 of total width or height
            x_buffer = extent_width / 10
            y_buffer = new_extent_height / 10
            extent = Extent(
                x_min=extent.x_min - x_buffer, y_min=extent.y_min - half_difference - y_buffer,
                x_max=extent.x_max + x_buffer, y_max=extent.y_max + half_difference + y_buffer)
        else:
            # height of the bbox is bigger. accommodate more width
            new_extent_width = image_ratio / extent_ratio * extent_width
            half_difference = (new_extent_width - extent_width) / 2
            # Add buffer of 1/10 of total width or height
            x_buffer = new_extent_width / 10
            y_buffer = extent_height / 10

            extent = Extent(
                x_min=extent.x_min - half_difference -  x_buffer, y_min=extent.y_min - y_buffer,
                x_max=extent.x_max + half_difference + x_buffer, y_max=extent.y_max + y_buffer)
        return extent

    def get_image_flood_summary_map(self, size):

        extent = self.get_flood_extent(self.flood_event_id)[0]
        extent = self.map_ratio_calculations(
            extent, size['width'] / size['height'])
        bbox = extent_to_string(extent)

        url = build_wms_url(self.wms_base_url, self.flood_event_id, bbox, size)
        path_map = download_map(url, f'flood_summary_map_{self.flood_event_id}.png')

        return path_map

    def get_image_country_flood_summary_map(self, instance, size):
        params = {
            'size': size,
            'table': 'country',
            'foreign_key': 'country_code',
            'area_code': int(instance.country_code),
            'image_name': f'district_{instance.country_code}_flood_summary_map_{self.flood_event_id}.png'
        }

        return self.get_map_path(params)

    def get_image_district_flood_summary_map(self, instance, size):
        params = {
            'size': size,
            'table': 'district',
            'foreign_key': 'dc_code',
            'area_code': int(instance.district_code),
            'image_name': f'district_{instance.district_code}_flood_summary_map_{self.flood_event_id}.png'
        }

        return self.get_map_path(params)

    def get_image_sub_district_flood_summary_map(self, instance, size):
        params = {
            'size': size,
            'table': 'sub_district',
            'foreign_key': 'sub_dc_code',
            'area_code': int(instance.sub_district_code),
            'image_name': f'sub_district_{instance.sub_district_code}_flood_summary_map_{self.flood_event_id}.png'
        }

        return self.get_map_path(params)

    def get_image_village_flood_summary_map(self, instance, size):
        params = {
            'size': size,
            'table': 'village',
            'foreign_key': 'village_code',
            'area_code': int(instance.village_code),
            'image_name': f'village_{instance.village_code}_flood_summary_map_{self.flood_event_id}.png'
        }

        return self.get_map_path(params)

    def get_map_path(self, params):
        extent = self.get_area_extent({
            'table': params['table'],
            'foreign_key': params['foreign_key']
        }, params['area_code'])[0]

        extent = self.map_ratio_calculations(
            extent, params['size']['width'] / params['size']['height'])

        bbox = extent_to_string(extent)

        url = build_wms_url(
            self.wms_base_url, self.flood_event_id, bbox, params['size'],
            table=params['table'], table_id=params['area_code'])

        path_map = download_map(url, params['image_name'])
        return path_map

    def apply_setting_set_paper(self, fd_current_sheet):
        # 8 is A3
        fd_current_sheet.set_paper(8)

    def apply_setting_center_horizontally(self, fd_current_sheet):
        fd_current_sheet.center_horizontally()

    def apply_setting_set_footer(self, fd_current_sheet):
        # https://xlsxwriter.readthedocs.io/page_setup.html#set_header
        fd_current_sheet.set_footer(
            '&LMade with love by&C&G&R&"Courier New,Bold"https://kartoza.com',
            {
                'image_center': self.get_image_kartoza_logo(None)
            }
        )


def build_wms_url(base_url, flood_event_id, bbox, size, styles='', table='', table_id=None):
    width = size['width']
    height = size['height']
    layer = 'hurricane_noaa_map'
    cql_filter = f'flood_event_id={flood_event_id}'
    image_format = 'image/png'
    params = {
        'service': 'WMS',
        'version': '1.1.1',
        'request': 'GetMap',
        'format': image_format,
        'transparent': True,
        'layers': layer,
        'cql_filter': cql_filter,
        'exceptions': 'application/vnd.ogc.se_inimage',
        'srs': 'EPSG:4326',
        'styles': styles,
        'width': width,
        'height': height,
        'bbox': bbox,
        'level': table,
        'area_id': table_id
    }

    query_params = urlencode(params)

    return f'{base_url}?{query_params}'


def extent_to_string(extent):
    return ','.join([
        str(extent.x_min),
        str(extent.y_min),
        str(extent.x_max),
        str(extent.y_max)
    ])


def download_map(url, image):
    maps_dir = '/tmp/fba-maps'

    if not os.path.exists(maps_dir):
        os.mkdir(maps_dir)

    path = os.path.join(
        maps_dir,
        image)

    response = requests.get(url, stream=True)

    with open(path, 'wb') as out_file:
        shutil.copyfileobj(response.raw, out_file)

    return path


def path_to_image(image):
    return os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        'images',
        image)
