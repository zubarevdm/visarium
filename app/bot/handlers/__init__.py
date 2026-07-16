from aiogram import Dispatcher

from app.bot.handlers import intake, payment, qa, settings, start


def register_all(dp: Dispatcher) -> None:
    # Порядок важен: qa ловит любой текст, поэтому подключается последним.
    dp.include_router(start.router)
    dp.include_router(settings.router)
    dp.include_router(payment.router)
    dp.include_router(intake.router)
    dp.include_router(qa.router)
