from __future__ import annotations

from datetime import date, timedelta

import discord

from discord.ext import commands

from sqlalchemy import (
    BigInteger,
    Column,
    Integer,
    String,
    Boolean,
    Date,
    ForeignKey,
    UniqueConstraint,
    event,
    exists,
    func,
    select,
)

from sqlalchemy.orm import relationship, column_property

from pie.database import database, session
from typing import List, Optional, Union

from ..school.database import Subject, Teacher

# TEACHER USAGE CHECK


def teacher_teacherreview_filter_generator():
    filter = exists().where(Teacher.idx == TeacherReview.teacher_id)
    return filter


def teacher_subjectreview_filter_generator():
    filter = exists().where(Teacher.idx == SubjectReview.guarantor_id)
    return filter


def teacher_is_used(teacher: Teacher) -> bool:
    query_teacher_review = (
        session.query(TeacherReview)
        .filter_by(TeacherReview.teacher_id == teacher.idx)
        .limit(1)
        .one_or_none()
        is not None
    )
    query_subject_review = (
        session.query(SubjectReview)
        .filter_by(SubjectReview.guarantor_id == teacher.idx)
        .limit(1)
        .one_or_none()
        is not None
    )

    return query_subject_review or query_teacher_review


Teacher.add_used_filter_generator(teacher_teacherreview_filter_generator)
Teacher.add_used_filter_generator(teacher_subjectreview_filter_generator)
Teacher.add_is_used_check(teacher_is_used)

# SUBJECT USAGE CHECK


def subject_subjectreview_filter_generator():
    filter = exists().where(Subject.idx == SubjectReview.subject_id)
    return filter


def subject_is_used(subject: Subject) -> bool:
    query_subject_review = (
        session.query(SubjectReview)
        .filter_by(SubjectReview.subject_id == subject.idx)
        .limit(1)
        .one_or_none()
        is not None
    )

    return query_subject_review


Subject.add_used_filter_generator(subject_subjectreview_filter_generator)
Subject.add_is_used_check(subject_is_used)


class SubjectRelevance(database.base):
    """Holds user votes for subject reviews.

    Args:
        voter_id: User's Discord ID
        vote: True if positive, False if negative
        review: SubjectReview IDX
    """

    __tablename__ = "school_review_subject_relevance"

    voter_id = Column(BigInteger, primary_key=True)
    vote = Column(Boolean, default=False)
    review = Column(
        Integer,
        ForeignKey("school_review_subject_review.idx", ondelete="CASCADE"),
        primary_key=True,
    )

    @staticmethod
    def reset(review_id: int):
        result = session.query(SubjectRelevance).filter_by(review=review_id).delete()
        session.commit()
        return result

    def __repr__(self) -> str:
        return (
            f'<{self.__class__.__name__} voter_id="{self.voter_id}" vote="{self.vote}" '
            f'review="{self.review}">'
        )

    def dump(self) -> dict:
        return {
            "voter_id": self.voter_id,
            "vote": self.vote,
            "review": self.review,
        }


class SubjectReview(database.base):
    """Holds information about subject reviews and all the logic.

    Args:
        idx: Unique review ID
        guild_id: Guild ID
        author_id: Author's Discord ID
        anonym: Show or hide author name
        subject_id: IDX of Subject
        grade: Grade as in school (should be 1-5)
        text_review: Text of review
        created: Date of creation
        updated: Date of update
        subject: Relationship with Subject
        guarantor: Relationship with Teacher (subject guarantor)
        relevance: Relationship with Votes (SubjectRelevance)
        upvotes: Count of positive votes
        downvotes: Count of negative votes
    """

    __tablename__ = "school_review_subject_review"
    __table_args__ = (
        UniqueConstraint(
            "author_id",
            "guild_id",
            "subject_id",
            name="guild_id_author_id_subject_id_unique",
        ),
    )

    idx = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger)
    author_id = Column(BigInteger)
    anonym = Column(Boolean, default=True)
    subject_id = Column(
        Integer, ForeignKey("school_dataset_subject.idx", ondelete="CASCADE")
    )
    guarantor_id = Column(
        Integer, ForeignKey("school_dataset_teacher.idx", ondelete="SET NULL")
    )
    grade = Column(Integer, default=0)
    text_review = Column(String, default=None)
    created = Column(Date)
    updated = Column(Date)
    subject = relationship("Subject")
    guarantor = relationship(lambda: Teacher)
    relevance = relationship("SubjectRelevance", cascade="all, delete-orphan, delete")

    upvotes = column_property(
        select([func.count(SubjectRelevance.voter_id)])
        .where(SubjectRelevance.review == idx)
        .where(SubjectRelevance.vote.is_(True))
        .scalar_subquery()
    )
    downvotes = column_property(
        select([func.count(SubjectRelevance.voter_id)])
        .where(SubjectRelevance.review == idx)
        .where(SubjectRelevance.vote.is_(False))
        .scalar_subquery()
    )

    def vote(self, user: Union[discord.User, discord.Member], vote: Optional[bool]):
        """Add or edit user's vote

        Args:
            user: Voting Discord user
            vote: True if upvote, False if downvote, None if delete
        """
        db_vote = (
            session.query(SubjectRelevance)
            .filter_by(review=self.idx)
            .filter_by(voter_id=user.id)
            .one_or_none()
        )

        if vote is None:
            if not db_vote:
                return

            session.delete(db_vote)
            session.commit()
            return

        if not db_vote:
            db_vote = SubjectRelevance(review=self.idx, voter_id=user.id)

        db_vote.vote = vote

        session.merge(db_vote)
        session.commit()

    def delete(self):
        """Delete review"""
        session.delete(self)
        session.commit()

    @staticmethod
    def avg_grade(subject: Subject) -> int:
        """Get average grade of subject"""
        query = session.query(func.avg(SubjectReview.grade)).filter(
            SubjectReview.subject_id == subject.idx
        )

        return query.scalar()

    @staticmethod
    def add(
        ctx: commands.Context, subject: Subject, grade: int, anonym: bool, text: str
    ) -> SubjectReview:
        """Add review information"""
        now = date.today()

        review = (
            session.query(SubjectReview)
            .filter_by(guild_id=ctx.guild.id)
            .filter_by(author_id=ctx.author.id)
            .filter_by(subject_id=subject.idx)
        )

        if review:
            if (date.today() - review.updated) > timedelta(days=30):
                SubjectRelevance.reset(review.idx)
        else:
            review = SubjectReview(
                guild_id=ctx.guild.id,
                author_id=ctx.author.id,
                subject_id=subject.idx,
                created=now,
            )

        review.anonym = anonym
        review.guarantor_id = subject.guarantor_id
        review.grade = grade
        review.text_review = text
        review.updated = now

        session.merge(review)
        session.commit()

        return review

    @staticmethod
    def get(
        ctx: commands.Context = None,
        subject: Subject = None,
        author: discord.Member = None,
        idx: int = None,
    ) -> List[SubjectReview]:
        """Get members subject review"""
        query = session.query(SubjectReview).filter_by(guild_id=ctx.guild.id)

        if subject:
            query = query.filter_by(subject_id=subject.idx)

        if author:
            query = query.filter_by(author_id=author.id)

        return query.all()

    def __repr__(self) -> str:
        return (
            f'<{self.__class__.__name__} idx="{self.idx}" guild_id="{self.guild_id}" '
            f'author_id="{self.author_id}" anonym="{self.anonym}" '
            f'subject_id="{self.subject_id}" guarantor_id={self.guarantor_id}" '
            f'grade="{self.grade}", text_review="{self.text_review}" created="{self.created}" '
            f'updated="{self.updated}" upvotes="{self.upvotes}" downvotes="{self.downvotes}">'
        )

    def dump(self) -> dict:
        return {
            "idx": self.idx,
            "guild_id": self.guild_id,
            "author_id": self.author_id,
            "anonym": self.anonym,
            "subject_id": self.subject_id,
            "guarantor_id": self.guarantor_id,
            "grade": self.grade,
            "text_review": self.text_review,
            "created": self.created,
            "updated": self.updated,
            "upvotes": self.upvotes,
            "downvotes": self.downvotes,
            "relevance": self.relevance,
        }


class TeacherRelevance(database.base):
    """Holds user votes for teacher reviews.

    Args:
        voter_id: User's Discord ID
        vote: True if positive, False if negative
        review: Teacher review IDX
    """

    __tablename__ = "school_review_teacher_relevance"

    voter_id = Column(BigInteger, primary_key=True)
    vote = Column(Boolean, default=False)
    review = Column(
        Integer,
        ForeignKey("school_review_teacher_review.idx", ondelete="CASCADE"),
        primary_key=True,
    )

    @staticmethod
    def reset(review_id: int):
        result = session.query(TeacherRelevance).filter_by(review=review_id).delete()
        session.commit()
        return result

    def __repr__(self) -> str:
        return (
            f'<{self.__class__.__name__} voter_id="{self.voter_id}" vote="{self.vote}" '
            f'review="{self.review}">'
        )

    def dump(self) -> dict:
        return {
            "voter_id": self.voter_id,
            "vote": self.vote,
            "review": self.review,
        }


class TeacherReview(database.base):
    """Holds information about teacher reviews and all the logic.

    Args:
        idx: Unique review ID
        guild_id: Guild ID
        author_id: Author's Discord ID
        anonym: Show or hide author name
        teacher_id: IDX of Teacher
        grade: Grade as in school (should be 1-5)
        text_review: Text of review
        created: Date of creation
        updated: Date of update
        teacher: Relationship with Teacher
        relevance: Relationship with Votes (TeacherRelevance)
        upvotes: Count of positive votes
        downvotes: Count of negative votes
    """

    __tablename__ = "school_review_teacher_review"
    __table_args__ = (
        UniqueConstraint(
            "author_id",
            "guild_id",
            "teacher_id",
            name="guild_id_author_id_teacher_id_unique",
        ),
    )

    idx = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger)
    author_id = Column(BigInteger)
    anonym = Column(Boolean, default=True)
    teacher_id = Column(
        Integer, ForeignKey("school_dataset_teacher.idx", ondelete="CASCADE")
    )
    grade = Column(Integer, default=0)
    text_review = Column(String, default=None)
    created = Column(Date)
    updated = Column(Date)
    teacher = relationship(lambda: Teacher)
    relevance = relationship("TeacherRelevance", cascade="all, delete-orphan, delete")

    upvotes = column_property(
        select([func.count(TeacherRelevance.voter_id)])
        .where(TeacherRelevance.review == idx)
        .where(TeacherRelevance.vote.is_(True))
        .scalar_subquery()
    )
    downvotes = column_property(
        select([func.count(TeacherRelevance.voter_id)])
        .where(TeacherRelevance.review == idx)
        .where(TeacherRelevance.vote.is_(False))
        .scalar_subquery()
    )

    def vote(self, user: Union[discord.User, discord.Member], vote: Optional[bool]):
        """Add or edit user's vote

        Args:
            user: Voting Discord user
            vote: True if upvote, False if downvote, None if delete
        """
        db_vote = (
            session.query(TeacherRelevance)
            .filter_by(review=self.idx)
            .filter_by(voter_id=user.id)
            .one_or_none()
        )

        if vote is None:
            if not db_vote:
                return

            session.delete(db_vote)
            session.commit()
            return

        if not db_vote:
            db_vote = TeacherRelevance(review=self.idx, voter_id=user.id)

        db_vote.vote = vote

        session.merge(db_vote)
        session.commit()

    def delete(self):
        """Delete review"""
        session.delete(self)
        session.commit()

    @staticmethod
    def avg_grade(teacher: Teacher) -> int:
        """Get average grade of teacher"""
        query = session.query(func.avg(TeacherReview.grade)).filter(
            TeacherReview.teacher_id == teacher.idx
        )

        return query.scalar()

    @staticmethod
    def add(
        ctx: commands.Context, teacher: Teacher, grade: int, anonym: bool, text: str
    ) -> TeacherReview:
        """Add review information"""
        now = date.today()

        review = (
            session.query(TeacherReview)
            .filter_by(guild_id=ctx.guild.id)
            .filter_by(author_id=ctx.author.id)
            .filter_by(teacher_id=teacher.idx)
        )

        if review:
            if (date.today() - review.updated) > timedelta(days=30):
                TeacherRelevance.reset(review.idx)
        else:
            review = SubjectReview(
                guild_id=ctx.guild.id,
                author_id=ctx.author.id,
                teacher_id=teacher.idx,
                created=now,
            )

        review.anonym = anonym
        review.grade = grade
        review.text_review = text
        review.updated = now

        session.merge(review)
        session.commit()

        return review

    @staticmethod
    def get(
        ctx: commands.Context = None,
        author: discord.Member = None,
        teacher: Teacher = None,
        idx: int = None,
    ) -> Optional[TeacherReview]:
        """Get members teacher review"""
        query = session.query(TeacherReview).filter_by(guild_id=ctx.guild.id)

        if author:
            query = query.filter_by(author_id=author.idx)

        if teacher:
            query = query.filter_by(teacher_id=teacher.idx)

        if idx:
            query = query.filter_by(idx=idx)

        return query.all()

    def __repr__(self) -> str:
        return (
            f'<{self.__class__.__name__} idx="{self.idx}" guild_id="{self.guild_id}" '
            f'author_id="{self.author_id}" anonym="{self.anonym}" teacher_id="{self.teacher_id}" '
            f'grade="{self.grade}", text_review="{self.text_review}" created="{self.created}" '
            f'updated="{self.updated}" upvotes="{self.upvotes}" downvotes="{self.downvotes}">'
        )

    def dump(self) -> dict:
        return {
            "idx": self.idx,
            "guild_id": self.guild_id,
            "author_id": self.author_id,
            "anonym": self.anonym,
            "teacher_id": self.teacher_id,
            "grade": self.grade,
            "text_review": self.text_review,
            "created": self.created,
            "updated": self.updated,
            "upvotes": self.upvotes,
            "downvotes": self.downvotes,
            "relevance": self.relevance,
        }


# GRADE CONSTRAINT


def grade_constraint_check(target, value, oldvalue, initiator):
    if value < 0 or value > 5:
        raise ValueError("Grade must be between 1 and 5")


event.listen(SubjectReview.grade, "set", grade_constraint_check)
event.listen(TeacherReview.grade, "set", grade_constraint_check)
