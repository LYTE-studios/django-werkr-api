import calendar
from django.utils import timezone
from datetime import date

from apps.jobs.models import Job, JobApplicationState, JobState, TimeRegistration
from django.db.models import Sum, F
from apps.core.utils.wire_names import *
from apps.jobs.models.application import JobApplication
from apps.core.utils.formatters import FormattingUtil


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
        ).aggregate(total_duration=Sum('duration'))['total_duration'] or timezone.timedelta()

        upcoming_hours = jobs.filter(
            job_state=JobState.pending
        ).annotate(
            duration=F('end_time') - F('start_time')
        ).aggregate(total_duration=Sum('duration'))['total_duration'] or timezone.timedelta()

        completed_jobs_count = jobs.filter(job_state=JobState.done).count()
        upcoming_jobs_count = jobs.filter(job_state=JobState.pending).count()

        daily_hours = {}
        today = date.today()
        for i in range(7):
            day = week_start + timezone.timedelta(days=i)
            daily_worked_hours = TimeRegistration.objects.filter(
                job__in=jobs,
                start_time__date=day
            ).annotate(
                duration=F('end_time') - F('start_time')
            ).aggregate(total_duration=Sum('duration'))['total_duration'] or timezone.timedelta()

            daily_hours[day.strftime("%a")] = (
                    daily_worked_hours.total_seconds() / 3600).__round__()  # Convert to hours

            if day > today:
                upcoming_work = jobs.filter(
                    start_time__date=day,
                    job_state=JobState.pending
                ).annotate(
                    duration=F('end_time') - F('start_time')
                ).aggregate(total_duration=Sum('duration'))['total_duration'] or timezone.timedelta()
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
        now = date.today()

        for month in range(1, 13):  # For each month in the year
            month_start = date(year, month, 1)
            next_month = month_start.replace(day=28) + timezone.timedelta(
                days=4)  # This will always move to the next month
            month_end = next_month - timezone.timedelta(days=next_month.day)

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
                ).aggregate(total_duration=Sum('duration'))['total_duration'] or timezone.timedelta()

                total_worked_hours = (worked_hours.total_seconds() / 3600).__round__()  # Convert to hours
            else:
                total_worked_hours = 0

            if month_start > now:
                upcoming_hours = jobs.filter(
                    job_state=JobState.pending
                ).annotate(
                    duration=F('end_time') - F('start_time')
                ).aggregate(total_duration=Sum('duration'))['total_duration'] or timezone.timedelta()

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


    def get_admin_statistics(start: timezone, end: timezone):
        if not start or not end:
            raise Exception("Invalid date range")

        jobs = Job.objects.filter(start_time__range=(start, end), archived=False)

        applications = []

        try:
            applications = JobApplication.objects.filter(job__in=jobs)
        except JobApplication.DoesNotExist:
            pass

        job_count = jobs.count()

        candidates = 0

        for job in jobs:
            candidates += job.max_workers

        planned_jobs_count = jobs.filter(
            selected_workers__gte=F("max_workers"),
        ).count()

        coming_jobs_count = jobs.filter(
            start_time__gt=timezone.now(),
        ).count()

        jobs_with_candidates = applications.values_list("job")

        jobs_without_candidates_count = jobs.count() - len(
            list(dict.fromkeys(jobs_with_candidates))
        )

        ongoing_jobs_count = jobs.filter(
            start_time__lt=timezone.now(), end_time__gt=timezone.now()
        ).count()

        completed_jobs_count = jobs.filter(
            job_state=JobState.done,
        ).count()

        unserviced_jobs_count = jobs.filter(
            job_state=JobState.pending,
            end_time__lte=timezone.now(),
        ).count()

        hours_worked_stats = StatisticsService.calculate_stats_for_range(start, end)

        trend_job_count = StatisticsService.calculate_trend_job_count(start, end)

        trend_hours_worked = StatisticsService.calculate_trend_hours_worked(start, end)

        return {
                k_jobs_count: job_count,
                k_candidates_count: candidates,
                k_planned_jobs_count: planned_jobs_count,
                k_coming_jobs_count: coming_jobs_count,
                k_ongoing_jobs_count: ongoing_jobs_count,
                k_completed_jobs_count: completed_jobs_count,
                k_jobs_without_candidates_count: jobs_without_candidates_count,
                k_unserviced_jobs_count: unserviced_jobs_count,
                k_hours_worked_stats: hours_worked_stats,
                k_trend_job_count: trend_job_count,
                k_trend_hours_worked: trend_hours_worked,
        }

    @staticmethod
    def get_customer_hours(customer_id: str):

        hours = (
            Job.objects.filter(
                customer_id=customer_id,
                archived=False,
                job_state=JobState.done,
            )
            .annotate(duration=F(k_end_time) - F(k_start_time))
            .aggregate(total_duration=Sum(k_duration))[k_total_duration]
        )

        if hours is None:
            return 0

        return (float(hours.seconds) / 3600).__round__()

    @staticmethod
    def calculate_trend_job_count(start, end):
        return Job.objects.filter(
            job_state__in=[JobState.pending, JobState.done],
            start_time__range=(
                start - (end - start),
                start,
            ),
        ).count()

    @staticmethod
    def calculate_trend_hours_worked(start, end):
        jobs = Job.objects.filter(
            job_state=JobState.done,
            start_time__range=(end, start - (end - start)),
        )

        return (
            TimeRegistration.objects.filter(
                job__in=jobs,
            )
            .annotate(duration=F(k_end_time) - F(k_start_time))
            .aggregate(total_duration=Sum(k_duration))[k_total_duration]
        )

    @staticmethod
    def calculate_stats_for_range(start, end):
        jobs = Job.objects.filter(
            start_time__range=(start, end),
            archived=False,
        )

        # actual hours worked
        worked_hours = (
            TimeRegistration.objects.filter(
                job__in=jobs, start_time__range=(start, end)
            )
            .annotate(duration=F(k_end_time) - F(k_start_time))
            .aggregate(total_duration=Sum(k_duration))[k_total_duration]
            or timezone.timedelta()
        )

        # upcoming job hours
        upcoming_hours = (
            jobs.filter(
                job_state=JobState.fulfilled,
                archived=False,
            )
            .annotate(duration=F(k_end_time) - F(k_start_time))
            .aggregate(total_duration=Sum(k_duration))[k_total_duration]
            or timezone.timedelta()
        )

        completed_jobs_count = jobs.filter(job_state=JobState.done).count()
        upcoming_jobs_count = jobs.filter(job_state=JobState.fulfilled).count()

        # calculate daily worked hours
        daily_hours = {}
        today = date.today()
        for i in range((end - start).days):
            day = (start + timezone.timedelta(days=i)).date()
            daily_worked_hours = (
                TimeRegistration.objects.filter(job__in=jobs, start_time__date=day)
                .annotate(duration=F(k_end_time) - F(k_start_time))
                .aggregate(total_duration=Sum(k_duration))[k_total_duration]
                or timezone.timedelta()
            )

            daily_hours[FormattingUtil.to_timestamp(day)] = (
                daily_worked_hours.total_seconds() / 3600
            ).__round__()  # Convert to hours

            if day > today:
                upcoming_work = (
                    jobs.filter(start_time__date=day, job_state=JobState.fulfilled)
                    .annotate(duration=F("end_time") - F("start_time"))
                    .aggregate(total_duration=Sum("duration"))["total_duration"]
                    or timezone.timedelta()
                )
                daily_hours[FormattingUtil.to_timestamp(day)] = (
                    upcoming_work.total_seconds() / 3600
                ).__round__()

        total_worked_hours = (
            worked_hours.total_seconds() / 3600
        ).__round__()  # Convert to hours
        total_upcoming_hours = (
            upcoming_hours.total_seconds() / 3600
        ).__round__()  # Convert to hours
        average_hours = (total_worked_hours / 7).__round__()  # 7 days in a week

        return {
            k_week_start: start.strftime("%Y-%m-%d"),
            k_week_end: end.strftime("%Y-%m-%d"),
            k_total_worked_hours: total_worked_hours,
            k_total_upcoming_hours: total_upcoming_hours,
            k_average_hours: average_hours,
            k_completed_jobs_count: completed_jobs_count,
            k_upcoming_jobs_count: upcoming_jobs_count,
            k_daily_hours: daily_hours,
        }
