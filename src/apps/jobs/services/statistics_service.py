import calendar
import datetime

from apps.jobs.models import Job, JobApplicationState, JobState, TimeRegistration
from django.db.models import Sum, F


class StatisticsService:

    @staticmethod
    def get_weekly_stats(worker_id, week_start, week_end):
        jobs = Job.objects.filter(
            start_time__range=(week_start, week_end),
            jobapplication__worker_id=worker_id,
            jobapplication__application_state=JobApplicationState.approved,
        )

        worked_hours = TimeRegistration.objects.filter(
            job__in=jobs,
            start_time__range=(week_start, week_end)
        ).annotate(
            duration=F('end_time') - F('start_time')
        ).aggregate(total_duration=Sum('duration'))['total_duration'] or datetime.timedelta()

        upcoming_hours = jobs.filter(
            job_state=JobState.pending
        ).annotate(
            duration=F('end_time') - F('start_time')
        ).aggregate(total_duration=Sum('duration'))['total_duration'] or datetime.timedelta()

        completed_jobs_count = jobs.filter(job_state=JobState.done).count()
        upcoming_jobs_count = jobs.filter(job_state=JobState.pending).count()

        daily_hours = {}
        today = datetime.date.today()
        for i in range(7):
            day = week_start + datetime.timedelta(days=i)
            daily_worked_hours = TimeRegistration.objects.filter(
                job__in=jobs,
                start_time__date=day
            ).annotate(
                duration=F('end_time') - F('start_time')
            ).aggregate(total_duration=Sum('duration'))['total_duration'] or datetime.timedelta()

            daily_hours[day.strftime("%a")] = (
                    daily_worked_hours.total_seconds() / 3600).__round__()  # Convert to hours

            if day > today:
                upcoming_work = jobs.filter(
                    start_time__date=day,
                    job_state=JobState.pending
                ).annotate(
                    duration=F('end_time') - F('start_time')
                ).aggregate(total_duration=Sum('duration'))['total_duration'] or datetime.timedelta()
                daily_hours[day.strftime("%a")] = (upcoming_work.total_seconds() / 3600).__round__()

        total_worked_hours = (worked_hours.total_seconds() / 3600).__round__()  # Convert to hours
        total_upcoming_hours = (upcoming_hours.total_seconds() / 3600).__round__()  # Convert to hours
        average_hours = (total_worked_hours / 7).__round__()  # 7 days in a week

        return {
            'week_start': week_start.strftime("%Y-%m-%d"),
            'week_end': week_end.strftime("%Y-%m-%d"),
            'total_worked_hours': total_worked_hours,
            'total_upcoming_hours': total_upcoming_hours,
            'average_hours': average_hours,
            'completed_jobs_count': completed_jobs_count,
            'upcoming_jobs_count': upcoming_jobs_count,
            'daily_hours': daily_hours
        }

    @staticmethod
    def get_monthly_stats(worker_id, year):
        monthly_stats = {}
        completed_jobs_year_count = 0
        upcoming_jobs_year_count = 0
        now = datetime.date.today()

        for month in range(1, 13):  # For each month in the year
            month_start = datetime.date(year, month, 1)
            next_month = month_start.replace(day=28) + datetime.timedelta(
                days=4)  # This will always move to the next month
            month_end = next_month - datetime.timedelta(days=next_month.day)

            jobs = Job.objects.filter(
                start_time__range=(month_start, month_end),
                jobapplication__worker_id=worker_id,
                jobapplication__application_state=JobApplicationState.approved,
            )

            completed_jobs_year_count += jobs.filter(job_state=JobState.done).count()
            upcoming_jobs_year_count += jobs.filter(job_state=JobState.pending).count()

            if month_start <= now:
                worked_hours = TimeRegistration.objects.filter(
                    job__in=jobs,
                    start_time__range=(month_start, month_end)
                ).annotate(
                    duration=F('end_time') - F('start_time')
                ).aggregate(total_duration=Sum('duration'))['total_duration'] or datetime.timedelta()

                total_worked_hours = (worked_hours.total_seconds() / 3600).__round__()  # Convert to hours
            else:
                total_worked_hours = 0

            if month_start > now:
                upcoming_hours = jobs.filter(
                    job_state=JobState.pending
                ).annotate(
                    duration=F('end_time') - F('start_time')
                ).aggregate(total_duration=Sum('duration'))['total_duration'] or datetime.timedelta()

                total_upcoming_hours = (upcoming_hours.total_seconds() / 3600).__round__()  # Convert to hours
            else:
                total_upcoming_hours = 0

            average_hours = total_worked_hours

            month_name = calendar.month_abbr[month]

            monthly_stats[month_name] = {
                'average_hours': average_hours,
                'total_upcoming_hours': total_upcoming_hours,
            }

        return {
            'year': year,
            'monthly_stats': monthly_stats,
            'completed_jobs_count': completed_jobs_year_count,
            'upcoming_jobs_count': upcoming_jobs_year_count
        }
