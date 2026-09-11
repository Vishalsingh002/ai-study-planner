from datetime import date, timedelta
from models import Subject, Task, Progress

class AIStudyRecommendationEngine:
    """
    Rule-based AI Recommendation System for intermediate-level AIML portfolio.
    Employs heuristic multi-criteria decision models, urgency scoring,
    and adaptive time-allocation scheduling.
    """

    @staticmethod
    def calculate_task_urgency_score(task):
        """
        Computes urgency score S in [0, 150] based on deadline proximity and priority.
        """
        days = (task.deadline - date.today()).days
        base_score = 0

        if days < 0:
            # Overdue tasks have critical urgency
            base_score = 100 + min(abs(days) * 5, 50)
        elif days == 0:
            base_score = 90  # Due today
        elif days == 1:
            base_score = 80  # Due tomorrow
        elif days <= 3:
            base_score = 65
        elif days <= 7:
            base_score = 45
        else:
            base_score = 20

        # Priority modifier weights
        priority_boost = {
            'High': 30,
            'Medium': 15,
            'Low': 0
        }.get(task.priority, 10)

        return base_score + priority_boost

    @classmethod
    def prioritize_tasks(cls, user_id, limit=6):
        """
        Ranks pending and in-progress tasks using the multi-criteria urgency score.
        """
        tasks = Task.query.join(Subject).filter(
            Subject.user_id == user_id,
            Task.status.in_(['Pending', 'In Progress'])
        ).all()

        scored_tasks = []
        for t in tasks:
            score = cls.calculate_task_urgency_score(t)
            scored_tasks.append((score, t))

        # Sort descending by calculated AI urgency score
        scored_tasks.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_tasks[:limit]]

    @classmethod
    def suggest_next_subject(cls, user_id):
        """
        Evaluates subjects using the Urgency & Deficit Index (UDI).
        Recommends which subject to tackle next with reasoning.
        """
        subjects = Subject.query.filter_by(user_id=user_id).all()
        if not subjects:
            return None

        best_subject = None
        max_udi_score = -1.0
        reason = ""

        for subj in subjects:
            pending_tasks = [t for t in subj.tasks if t.status != 'Completed']
            completed_tasks = [t for t in subj.tasks if t.status == 'Completed']
            total = len(subj.tasks)

            if total == 0:
                continue

            completion_rate = completed_tasks / total
            deficit = 1.0 - completion_rate  # 0.0 to 1.0

            # Calculate urgency sum of pending tasks
            urgency_sum = sum(cls.calculate_task_urgency_score(t) for t in pending_tasks)
            urgency_factor = urgency_sum / (len(pending_tasks) if pending_tasks else 1)

            # UDI formula: 45% deficit weight, 55% task urgency weight
            udi_score = (deficit * 45.0) + (urgency_factor * 0.55)

            # Check for overdue tasks
            overdue_count = sum(1 for t in pending_tasks if t.is_overdue)
            if overdue_count > 0:
                udi_score += 25.0

            if udi_score > max_udi_score:
                max_udi_score = udi_score
                best_subject = subj
                if overdue_count > 0:
                    reason = f"{overdue_count} overdue task(s) require immediate remediation."
                elif deficit > 0.6:
                    reason = f"Low completion velocity ({subj.completion_rate}%). Needs syllabus coverage."
                else:
                    reason = "Upcoming high-priority deadlines approaching soon."

        if not best_subject:
            # Fallback to first available subject
            best_subject = subjects[0]
            reason = "Default recommendation. Add tasks to activate AI heuristic weighting."

        return {
            'subject': best_subject,
            'score': round(max_udi_score, 1),
            'reason': reason
        }

    @classmethod
    def recommend_study_hours(cls, user_id):
        """
        Recommends subject-specific hours based on completion lag and task count.
        """
        subjects = Subject.query.filter_by(user_id=user_id).all()
        allocations = []

        for subj in subjects:
            pending_hours = sum(t.estimated_hours for t in subj.tasks if t.status != 'Completed')
            if pending_hours <= 0:
                continue

            # Subjects with low completion get 1.4x factor
            rate = subj.completion_rate
            multiplier = 1.4 if rate < 50.0 else 1.0
            suggested_allocation = round(pending_hours * multiplier * 0.4, 1)  # Daily chunk
            suggested_allocation = max(0.5, min(suggested_allocation, 4.0))

            allocations.append({
                'subject_name': subj.subject_name,
                'color': subj.color,
                'suggested_hours': suggested_allocation,
                'completion_rate': rate
            })

        allocations.sort(key=lambda x: x['suggested_hours'], reverse=True)
        return allocations

    @classmethod
    def generate_daily_schedule(cls, user_id, target_hours=4.0):
        """
        Generates an automated daily study timetable with 45-min Pomodoro focus blocks
        and 10-minute breaks, mapped to prioritized tasks.
        """
        prioritized_tasks = cls.prioritize_tasks(user_id, limit=5)
        timetable = []

        current_time = timedelta(hours=9, minutes=0)  # Start at 09:00 AM
        remaining_minutes = int(target_hours * 60)
        block_duration = 50  # 45m study + 5m switch
        break_duration = 10

        task_idx = 0
        while remaining_minutes >= 30 and task_idx < len(prioritized_tasks):
            task = prioritized_tasks[task_idx]
            session_minutes = min(block_duration, remaining_minutes)

            start_str = (datetime.min + current_time).strftime("%I:%M %p")
            end_time = current_time + timedelta(minutes=session_minutes)
            end_str = (datetime.min + end_time).strftime("%I:%M %p")

            timetable.append({
                'time_slot': f"{start_str} - {end_str}",
                'task_name': task.task_name,
                'subject_name': task.subject.subject_name,
                'color': task.subject.color,
                'duration': f"{session_minutes} mins",
                'is_break': False
            })

            current_time = end_time
            remaining_minutes -= session_minutes

            # Insert scheduled break if time permits
            if remaining_minutes >= break_duration:
                break_end = current_time + timedelta(minutes=break_duration)
                timetable.append({
                    'time_slot': f"{end_str} - {(datetime.min + break_end).strftime('%I:%M %p')}",
                    'task_name': "Cognitive Rest & Hydration Break",
                    'subject_name': "Recovery",
                    'color': "#10b981",
                    'duration': "10 mins",
                    'is_break': True
                })
                current_time = break_end
                remaining_minutes -= break_duration

            task_idx += 1

        return timetable

    @classmethod
    def generate_productivity_tips(cls, user):
        """
        Yields context-aware productivity recommendations based on user performance.
        """
        tips = []
        streak = user.get_study_streak()
        overdue_count = Task.query.join(Subject).filter(
            Subject.user_id == user.id,
            Task.status != 'Completed',
            Task.deadline < date.today()
        ).count()

        if overdue_count > 0:
            tips.append({
                'icon': 'bi-exclamation-triangle-fill',
                'type': 'warning',
                'text': f"You have {overdue_count} overdue task(s). Prioritize quick wins to reset your momentum."
            })

        if streak >= 3:
            tips.append({
                'icon': 'bi-fire',
                'type': 'success',
                'text': f"Impressive {streak}-day study streak! Habit consistency boosts cognitive retention by over 40%."
            })
        else:
            tips.append({
                'icon': 'bi-lightning-charge',
                'type': 'info',
                'text': "Log at least 30 minutes today to build or sustain your daily study streak."
            })

        tips.append({
            'icon': 'bi-clock-history',
            'type': 'primary',
            'text': "Follow the 45/10 Pomodoro rule to prevent fatigue and retain complex AIML/engineering topics."
        })

        return tips