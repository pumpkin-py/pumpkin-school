from __future__ import annotations

from typing import List, Optional

from sqlalchemy import BigInteger, Column, Table, ForeignKey
from sqlalchemy.orm import relationship

from pie.database import database, session

association_table = Table(
    "association",
    database.base.metadata,
    Column(
        "t_channel_id",
        BigInteger,
        ForeignKey(
            "school_teacherchannel_teacherchannel.t_channel_id", ondelete="CASCADE"
        ),
    ),
    Column(
        "teacher_id",
        BigInteger,
        ForeignKey("school_teacherchannel_teacher.teacher_id", ondelete="CASCADE"),
    ),
)


class TeacherChannel(database.base):
    """Subject channels containing teacher channel, synced from the original channel.
    t_channel is the new teacher channel, o_channel is original."""

    __tablename__ = "school_teacherchannel_teacherchannel"

    t_channel_id = Column(BigInteger, primary_key=True, autoincrement=False)
    guild_id = Column(BigInteger)
    o_channel_id = Column(BigInteger, unique=True)
    teachers = relationship(
        "Teachers",
        secondary=association_table,
        back_populates="channels",
        cascade="all, delete",
    )

    @staticmethod
    def add(
        guild_id: int, t_channel_id: int, o_channel_id: int, teacher_id: int
    ) -> TeacherChannel:
        teacherchannel = (
            session.query(TeacherChannel)
            .filter_by(
                guild_id=guild_id, t_channel_id=t_channel_id, o_channel_id=o_channel_id
            )
            .one_or_none()
        )
        teacher = Teachers.get(teacher_id)
        if not teacher:
            teacher = Teachers(teacher_id=teacher_id)
        if not teacherchannel:
            teacherchannel = TeacherChannel(
                guild_id=guild_id, t_channel_id=t_channel_id, o_channel_id=o_channel_id
            )
            teacherchannel.teachers.append(teacher)
            session.add(teacherchannel)
        elif teacher_id not in [i.teacher_id for i in teacherchannel.teachers]:
            teacherchannel.teachers.append(teacher)
            session.merge(teacherchannel)
        session.commit()
        return teacherchannel

    @staticmethod
    def get_all(guild_id: int) -> List[TeacherChannel]:
        return session.query(TeacherChannel).filter_by(guild_id=guild_id).all()

    @staticmethod
    def get(guild_id: int, o_channel_id: int) -> Optional[TeacherChannel]:
        return (
            session.query(TeacherChannel)
            .filter_by(guild_id=guild_id, o_channel_id=o_channel_id)
            .one_or_none()
        )

    @staticmethod
    def get_by_t_channel(guild_id: int, t_channel_id: int) -> Optional[TeacherChannel]:
        return (
            session.query(TeacherChannel)
            .filter_by(guild_id=guild_id, t_channel_id=t_channel_id)
            .one_or_none()
        )

    @staticmethod
    def remove(guild_id: int, t_channel_id: int, teacher_id: int):
        teacherchannel = (
            session.query(TeacherChannel)
            .filter_by(guild_id=guild_id, t_channel_id=t_channel_id)
            .one_or_none()
        )
        # searching for related objects
        for teacher in teacherchannel.teachers:
            if teacher.teacher_id == teacher_id:
                teacherchannel.teachers.remove(teacher)
                session.commit()
                break
        if len(teacherchannel.teachers) < 1:
            session.delete(teacherchannel)
        else:
            session.merge(teacherchannel)
        session.commit()

    @staticmethod
    def get_guilds() -> List[TeacherChannel]:
        return (
            session.query(TeacherChannel.guild_id)
            .distinct(TeacherChannel.guild_id)
            .all()
        )

    def __repr__(self) -> str:
        return (
            f"<TeacherChannel guild_id='{self.guild_id}' "
            f"t_channel_id='{self.t_channel_id}' o_channel_id='{self.o_channel_id}' "
            f"teachers=[{'; '.join([str(i.teacher_id) for i in self.teachers])}]>"
        )

    def dump(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "t_channel_id": self.t_channel_id,
            "o_channel_id": self.o_channel_id,
            "teachers": [i.teacher_id for i in self.teachers],
        }


class Teachers(database.base):
    """Teachers of a channel"""

    __tablename__ = "school_teacherchannel_teacher"

    teacher_id = Column(BigInteger, primary_key=True, autoincrement=False)
    channels = relationship(
        "TeacherChannel",
        secondary=association_table,
        back_populates="teachers",
        passive_deletes=True,
    )

    @staticmethod
    def get(teacher_id: int) -> Optional[Teachers]:
        return session.query(Teachers).filter_by(teacher_id=teacher_id).one_or_none()

    def __repr__(self):
        return (
            f"<Teachers teacher_id='{self.teacher_id}' "
            f"channels=[{'; '.join([str(i.t_channel_id) for i in self.channels])}]>"
        )

    def dump(self) -> dict:
        return {
            "teacher_id": self.teacher_id,
            "channels": [i.t_channel_id for i in self.channels],
        }
