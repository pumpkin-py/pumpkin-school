from __future__ import annotations

from datetime import date
from typing import Optional

import discord

from pie.database import database, session

from sqlalchemy import (
    BigInteger,
    Integer,
    Boolean,
    String,
    Date,
    Column,
    PrimaryKeyConstraint,
    ForeignKey,
)
from sqlalchemy.orm import relationship


class Review(database.base):
    __tablename__ = "school_reviews_reviews"

    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger)
    discord_id = Column(BigInteger)
    anonym = Column(Boolean, default=True)
    subject = Column(String, ForeignKey("school_reviews_subjects.shortcut"))
    subject_object = relationship("Subject")
    tier = Column(Integer, default=0)
    text_review = Column(String, default=None)
    date = Column(Date)
    relevance: list[ReviewRelevance] = relationship(
        "ReviewRelevance", back_populates="review_object"
    )

    @staticmethod
    def get_all(guild: discord.Guild) -> list[Review]:
        return session.query(Review).filter_by(guild_id=guild.id).all()

    @staticmethod
    def get(review_id: int) -> Optional[Review]:
        return session.query(Review).filter_by(id=review_id).one_or_none()

    @staticmethod
    def get_for_user(user: discord.User) -> list[Review]:
        return session.query(Review).filter_by(discord_id=user.id).all()

    def vote_up(self, user: discord.User):
        for relevance_review in self.relevance:
            if relevance_review.discord_id == user.id:
                relevance_review.vote = True
                session.commit()
                return
        self.relevance.append(
            ReviewRelevance(discord_id=user.id, vote=True, review=self)
        )
        session.merge(self)
        session.commit()

    def vote_down(self, user: discord.User):
        for relevance_review in self.relevance:
            if relevance_review.discord_id == user.id:
                relevance_review.vote = False
                session.commit()
                return
        self.relevance.append(
            ReviewRelevance(discord_id=user.id, vote=False, review=self)
        )
        session.merge(self)
        session.commit()

    def vote_neutral(self, user: discord.User):
        session.query(ReviewRelevance).filter_by(
            discord_id=user.id, review=self.id
        ).delete()
        session.merge(self)
        session.commit()

    def get_positive_votes(self) -> int:
        return len(list(filter(lambda x: x.vote, self.relevance)))

    def get_negative_votes(self) -> int:
        return len(list(filter(lambda x: not x.vote, self.relevance)))

    @staticmethod
    def add(
        guild: discord.Guild,
        author: discord.User,
        subject_abbreviation: str,
        mark: int,
        anonymous: bool,
        text: str,
    ):
        subject_object = Subject.get(subject_abbreviation)
        review = (
            session.query(Review)
            .filter_by(
                guild_id=guild.id, discord_id=author.id, subject=subject_abbreviation
            )
            .one_or_none()
        )
        if review is not None:
            # Just update the already existing object
            review.mark = mark
            review.anonym = anonymous
            review.text_review = text
            review.date = date.today()
            for relevance_opinion in review.relevance:
                session.delete(relevance_opinion)
        else:
            review = Review(
                guild_id=guild.id,
                discord_id=author.id,
                anonym=anonymous,
                subject=subject_abbreviation,
                tier=mark,
                text_review=text,
                date=date.today(),
            )
        review.subject_object = subject_object
        session.add(review)
        session.commit()
        return review

    @staticmethod
    def remove(
        guild: discord.Guild, user: discord.User, subject_abbreviation: str
    ) -> bool:
        ret_val = (
            session.query(Review)
            .filter_by(
                guild_id=guild.id, discord_id=user.id, subject=subject_abbreviation
            )
            .delete()
            > 0
        )
        session.commit()
        return ret_val


class ReviewRelevance(database.base):
    __tablename__ = "school_reviews_relevance"
    __table_args__ = (PrimaryKeyConstraint("review", "discord_id", name="key"),)

    discord_id = Column(BigInteger)
    vote = Column(Boolean, default=False)
    review = Column(Integer, ForeignKey("school_reviews_reviews.id"))
    review_object = relationship("Review", back_populates="relevance")


class Subject(database.base):
    __tablename__ = "school_reviews_subjects"

    shortcut = Column(String, primary_key=True)
    category = Column(String)
    name = Column(String)
    reviews = relationship("Review", back_populates="subject_object")

    def __repr__(self):
        return f"<Subject shortcut={self.shortcut} name={self.name} category={self.category}>"

    def __str__(self):
        return f"{self.shortcut}: {self.name} ({self.category})"

    @staticmethod
    def get(abbreviation: str) -> Optional[Subject]:
        """Fetch subject from DB. Case-insensitive."""
        return (
            session.query(Subject)
            .filter_by(shortcut=abbreviation.lower())
            .one_or_none()
        )

    @staticmethod
    def add(abbreviation: str, name: str, category: str):
        subject = session.query(Subject).filter_by(shortcut=abbreviation).one_or_none()
        if subject is not None:
            subject.name = name
            subject.category = category
            session.merge(subject)
            session.commit()
            return
        subject = Subject(name=name, category=category, shortcut=abbreviation)
        session.add(subject)
        session.commit()

    @staticmethod
    def remove(abbreviation: str) -> bool:
        return session.query(Subject).filter_by(shortcut=abbreviation).delete() > 0
