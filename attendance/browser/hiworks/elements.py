from dataclasses import dataclass


@dataclass(frozen=True)
class LoginElement:
    input_id: str = '#office_id'
    input_pass: str = '#office_passwd'
    login_btn: str = '.int_jogin'


@dataclass(frozen=True)
class Check:
    wrap_class: str = '.today-status'
    open_div_btn: str = '.hw-button'
    detail: str = '.today-detail'

    check_btn: str = 'button'
    check_text_div: str = '.check-btn'
    check_text_content: str = ''
    check_time_div: str = '.check-time'


@dataclass(frozen=True)
class Checkin(Check):
    check_text_content: str = '출근하기'
    index: int = 0


@dataclass(frozen=True)
class Checkout(Check):
    check_text_content: str = '퇴근하기'
    index: int = 1
