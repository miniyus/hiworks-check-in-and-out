import os
import time
import subprocess
from datetime import datetime, date
from configparser import ConfigParser
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from hciao.browser.chrome import Chrome
from hciao.browser.abstracts import Browser
from hciao.logger.log import Log
from hciao.browser.hiworks.elements import Checkin, Checkout, Check
from hciao.browser.login_data import LoginData
from hciao.logger.logger_adapter import LoggerAdapter
from hciao.mailer.abstracts import Mailer
from hciao.schedule.checker import Checker
from hciao.utils import date as util_dt
from hciao.database.drivers.local import LocalSchema, LocalDriver
from hciao.database.drivers.abstracts import Driver
from hciao.mailer.mailer import SimpleMailer


class Worker:
    __constants: dict[str, str]
    __logger: LoggerAdapter
    __data_store: Driver
    __browser: Browser
    __mailer: Mailer
    __configs: dict[str, ConfigParser]
    __checker: Checker

    def __init__(self, constants: dict[str, str]):
        """
        Worker Constructor
        :param constants: 상수 값
        :type: constants: Dict[str, str]
        """
        now = datetime.now()

        self.__constants = constants
        self.__configs = {
            'hiworks': self.__config('../hiworks.ini'),
            'mailer': self.__config('../mailer.ini')
        }
        self.__logger = self.__get_logger('worker')

        self.__data_store = self.__get_local_storage(self.__constants['database'])
        self.__mailer = self.__get_mailer(self.__configs['mailer'])
        self.__browser = self.__get_browser(self.__logger.prefix, self.__configs['hiworks']['default']['url'])
        self.__checker = Checker(self.__data_store)

        self.__logger.debug('start up worker')

        data = LocalSchema()
        if self.__data_store.get(data, now.strftime('%Y-%m-%d')) is None:
            self.__logger.info('daily pip update...')
            subprocess.run(f"pip3 install -r {constants['base_path']}/../requirements.txt", shell=True)

    @classmethod
    def __config(cls, file_path: str) -> ConfigParser:
        """
        get config parser
        :param file_path:
        :type file_path: str
        :return: config
        :rtype: ConfigParser
        """
        current_path = os.path.dirname(os.path.abspath(__file__))
        config_parser = ConfigParser()
        config_parser.read(os.path.join(current_path, file_path))
        return config_parser

    @classmethod
    def __get_logger(cls, tag: str) -> LoggerAdapter:
        """
        get logger
        :param tag: tag for logging
        :return: Logger
        :rtype: LoggerAdapter
        """
        return Log.logger(tag)

    @classmethod
    def __get_browser(cls, tag: str, url: str) -> Browser:
        """
        get browser
        :param tag:
        :param url:
        :return: browser
        :rtype: Browser
        """
        options = webdriver.ChromeOptions()
        options.add_argument('headless')
        service = Service(ChromeDriverManager().install())

        return Chrome(
            cls.__get_logger(tag),
            webdriver.Chrome(service=service, options=options),
            url
        )

    @classmethod
    def __get_local_storage(cls, path: str) -> Driver:
        """
        get local storage
        :param path:
        :type path: str
        :return: local storage driver
        :rtype: Driver
        """

        return LocalDriver({'path': path})

    @classmethod
    def __get_mailer(cls, mail_config: dict) -> Mailer:
        """
        get mailer
        :param mail_config:
        :return: mailer
        :rtype: Mailer
        """
        return SimpleMailer(
            host=mail_config['outlook']['url'],
            login_id=mail_config['outlook']['id'],
            login_pass=mail_config['outlook']['password']
        )

    def checkin(self, login_id: str, passwd: str) -> int:
        """
        출근하기
        :param login_id:
        :type login_id: str
        :param passwd:
        :type passwd: str
        :return: return 0 is success other value is fail
        :rtype: int
        """
        self.__logger.info('try checkin...')

        if util_dt.is_holidays(date=date.today()):
            self.__logger.info('today is holiday')
            return 1

        browser = self.__browser
        data_store = self.__data_store
        conf = self.__configs['hiworks']

        if login_id is None or passwd is None:
            login_id = conf['default']['id']
            passwd = conf['default']['password']

        check_time = browser.checkin(LoginData(login_id=login_id, login_pass=passwd), Checkin())

        now = datetime.now()

        data = LocalSchema()
        data.login_id = login_id
        data.checkout_at = None
        data.work_hour = None

        if check_time is None and check_time == '00:00:00':
            data.checkin_at = now.strftime('%Y-%m-%d')
        else:
            data.checkin_at = check_time

        if data_store.save(now.strftime('%Y-%m-%d'), data):
            return 0

        return 1

    def checkout(self, login_id: str = None, passwd: str = None) -> int:
        """
        퇴근
        :param login_id:
        :param passwd:
        :type login_id: str | None
        :type passwd: str | None
        :return: return 0 is success other value is fail
        :rtype: int
        """
        self.__logger.info('try checkout...')

        if util_dt.is_holidays(date=date.today()):
            self.__logger.info('today is holiday')
            return 1

        conf = self.__configs['hiworks']
        browser = self.__browser
        data_store = self.__data_store

        if login_id is None or passwd is None:
            login_id = conf['default']['id']
            passwd = conf['default']['password']

        check_time = browser.checkout(LoginData(login_id=login_id, login_pass=passwd), Checkout())

        now = datetime.now()
        data = LocalSchema()
        data = data_store.get(data, now.strftime('%Y-%m-%d'))

        if data is not None and isinstance(data, LocalSchema):
            if check_time is None and check_time == '00:00:00':
                data.checkout_at = now.strftime('%H:%M:%S')
            else:
                data.checkout_at = check_time

            out_time = time.strptime(data.checkout_at, '%H:%M:%S')
            in_time = time.strptime(data.checkin_at, '%H:%M:%S')

            data.work_hour = util_dt.seconds_to_hours(time.mktime(out_time) - time.mktime(in_time))
            data_store.save(now.strftime('%Y-%m-%d'), data)

        return 0

    def check_work_hour(self) -> int:
        """
        check today work hour

        :return:
        :rtype: int
        """
        self.__logger.info('check work hour...')

        now = datetime.now()

        logger = self.__logger
        data_store = self.__data_store

        data = LocalSchema()
        data = data_store.get(data, now.strftime('%Y-%m-%d'))
        if data is None and not isinstance(data, LocalSchema):
            logger.info('not yet checkin')
            return 1

        if data.checkin_at is None:
            logger.info('not yet checkin')
            return 1

        if data.work_hour is not None:
            logger.info(f"already checkout: {data.checkout_at}")
            logger.info(f"work hours: {data.work_hour}")
        else:
            work = self.__checker.get_work_hour_today()
            logger.info(f"work hours: {util_dt.seconds_to_hours(work.work)}")

            if work.left > 0:
                logger.info(f"left hours: {util_dt.seconds_to_hours(work.left)}")
            else:
                logger.info(f"over hours: {util_dt.seconds_to_hours(work.left)}")
        return 0

    def check_and_alert(self) -> int:
        """
        check left time and  when over work time, send alert mail

        :return: 0: success, other value: fail
        :rtype: int
        """
        self.__logger.info('check and alert')

        logger = self.__logger
        conf = self.__configs['hiworks']
        browser = self.__browser
        data_store = self.__data_store

        now = datetime.now()

        login_id = conf['default']['id']
        passwd = conf['default']['password']

        check_time = browser.check_work(LoginData(login_id, passwd), Check())

        if check_time is not None:
            data = LocalSchema()
            data = data_store.get(data, now.strftime('%Y-%m-%d'))
            if isinstance(data, LocalSchema):
                data.checkin_at = check_time['checkin_at']
                data.checkout_at = check_time['checkout_at']
                data_store.save(now.strftime('%Y-%m-%d'), data)

        data = LocalSchema()
        data = data_store.get(data, now.strftime('%Y-%m-%d'))

        is_checkin = True
        if data is None and not isinstance(data, LocalSchema):
            logger.error('you are not checkin')
            is_checkin = False

        elif data.checkin_at is None:
            logger.debug('not yet checkin')
            is_checkin = False

        hiworks = self.__configs['hiworks']
        mail_config = self.__configs['mailer']
        mailer = self.__mailer

        if not is_checkin:
            mailer.send(mail_config['outlook']['id'], f"[Alert] You Don't Checkin...",
                        f"go: {hiworks['default']['url']}")

        if data.work_hour is not None:
            logger.debug(f"already checkout: {data.checkout_at}")
            logger.info(f"work hours: {data.work_hour}")
        else:
            checker = Checker(data_store)
            work = checker.get_work_hour_today()
            logger.info(f"work hours: {util_dt.seconds_to_hours(work.work)}")
            if work.left > 0:
                logger.info(f"left hours: {util_dt.seconds_to_hours(work.left)}")

                if data.checkout_at is not None:
                    logger.debug(f"already checkout: {data.checkout_at}")
            else:
                logger.info(f"over hours: {util_dt.seconds_to_hours(work.left)}")

            if work.left <= 600:
                logger.debug(f"you must checkout!!")

                mailer.send(mail_config['outlook']['id'], '[Alert] You must checkout!!',
                            f"You must checkout, left {util_dt.seconds_to_hours(work.left)}")

        return 0

    def test(self):
        """
        just test
        :return: void
        :rtype: None
        """
        self.__logger.info('try test...')

        hiworks = self.__configs['hiworks']

        check_time = self.__browser.check_work(
            LoginData(login_id=hiworks['default']['id'], login_pass=hiworks['default']['password']),
            Check()
        )

        if check_time is not None:
            self.__logger.debug(f"checkin_at: {check_time['checkin_at']}")
            self.__logger.debug(f"checkout_at: {check_time['checkout_at']}")