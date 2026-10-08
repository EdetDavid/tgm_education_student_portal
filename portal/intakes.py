import calendar

from django.utils import timezone


def available_intakes(months):
    today = timezone.localdate()
    month_numbers = {name: index for index,
                     name in enumerate(calendar.month_name) if name}
    return [f'{month} {year}'
            for year in range(today.year, today.year + 5)
            for month in months
            if month in month_numbers and (year, month_numbers[month]) >= (today.year, today.month)]
