from __future__ import annotations

import enum

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
    func,
    not_,
)
from sqlalchemy.orm import relationship
from typing import Callable, Dict, List, Optional

from pie import i18n
from pie.database import database, session

_ = i18n.Translator("modules/school").translate

# M:N table to connect teachers with subjects
teachers_subjects = Table(
    "school_dataset_teachers_subjects",
    database.base.metadata,
    Column(
        "subject",
        ForeignKey("school_dataset_subject.idx", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "teacher",
        ForeignKey("school_dataset_teacher.idx", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Semester(enum.Enum):
    """Enum for semester"""

    SUMMER = "SUMMER"
    WINTER = "WINTER"
    BOTH = "BOTH"

    @staticmethod
    def from_bool(winter_semester: bool, summer_semester: bool) -> Semester:
        if winter_semester and summer_semester:
            return Semester.BOTH
        elif winter_semester:
            return Semester.WINTER
        else:
            return Semester.SUMMER

    @staticmethod
    def get_formatted_list(ctx) -> str:
        """Returns translated list of valid semesters.

        Args:
            ctx: Translation context

        Returns:
            Formated list of valid semesters
        """
        list = ""
        for semester in Semester:
            list += (
                "\n**"
                + semester.value
                + "** "
                + _(ctx, "for")
                + " "
                + semester.translate(ctx)
            )
        return list

    def translate(self, ctx) -> str:
        """Translate semester

        Args:
            ctx: Translation context

        Returns:
            Translated human-readable semester
        """
        if self == Semester.SUMMER:
            return _(ctx, "Summer")
        elif self == Semester.WINTER:
            return _(ctx, "Winter")
        elif self == Semester.BOTH:
            return _(ctx, "Both")
        else:
            return "-"


class ProgramType(enum.Enum):
    """Enum for program type"""

    FULLTIME = "F"
    DISTANCE = "D"
    UNKNOWN = "-"

    @staticmethod
    def from_shortcut(shortcut: str) -> ProgramType:
        """Get ProgramType based on shortcut.

        Args:
            shortcut: Shortcut of program type

        Returns:
            ProgramType based on shortcut or ProgramType.UNKNOWN if unknown
        """
        shortcut = shortcut.upper()
        try:
            program_type = ProgramType(shortcut)
        except ValueError:
            return ProgramType.UNKNOWN

        return program_type

    @staticmethod
    def get_formatted_list(ctx) -> str:
        """Returns translated list of valid
        program types.

        Args:
            ctx: Translation context

        Returns:
            Formated list of valid degrees
        """
        list = ""
        for program_type in ProgramType:
            if program_type == ProgramType.UNKNOWN:
                continue
            list += (
                "\n**"
                + program_type.value
                + "** "
                + _(ctx, "for")
                + " "
                + program_type.translate(ctx)
            )
        return list

    def translate(self, ctx) -> str:
        """Translate program type

        Args:
            ctx: Translation context

        Returns:
            Translated human-readable program type
        """
        if self == ProgramType.FULLTIME:
            return _(ctx, "Full-time")
        elif self == ProgramType.DISTANCE:
            return _(ctx, "Distance")
        else:
            return "-"


class Degree(enum.Enum):
    BACHELOR = "B"
    DOCTORAL = "D"
    MASTERS = "M"
    UNKNOWN = "-"

    @staticmethod
    def from_shortcut(shortcut: str) -> Degree:
        """Get Degree based on shortcut.

        Args:
            shortcut: Shortcut of degree

        Returns:
            Degree based on shortcut or Degree.UNKNOWN if unknown
        """
        shortcut = shortcut.upper()
        if shortcut == "N":
            shortcut = "M"

        try:
            degree = Degree(shortcut)
        except ValueError:
            return Degree.UNKNOWN

        return degree

    @staticmethod
    def get_formatted_list(ctx) -> str:
        """Returns translated list of valid degrees.

        Args:
            ctx: Translation context

        Returns:
            Formated list of valid degrees
        """
        list = ""
        for degree in Degree:
            if degree == Degree.UNKNOWN:
                continue
            list += (
                "\n**"
                + degree.value
                + "** "
                + _(ctx, "for")
                + " "
                + degree.translate(ctx)
            )
        return list

    def translate(self, ctx) -> str:
        """Translate degree

        Args:
            ctx: Translation context

        Returns:
            Translated human-readable degree
        """
        if self == Obligation.BACHELOR:
            return _(ctx, "Bachelor")
        elif self == Obligation.DOCTORAL:
            return _(ctx, "Doctoral")
        elif self == Obligation.MASTERS:
            return _(ctx, "Masters")
        else:
            return "-"


class Obligation(enum.Enum):
    OPTIONAL = "O"
    OPTIONAL_SPECIALIZED = "VO"
    COMPULSORY_OPTIONAL = "PV"
    COMPULSORY = "V"
    RECOMMENDED = "D"
    OTHER = "O"

    @staticmethod
    def get_formatted_list(ctx) -> str:
        """Returns translated list of valid obligations.

        Args:
            ctx: Translation context

        Returns:
            Formated list of valid obligations
        """
        list = ""
        for obligation in Obligation:
            list += (
                "\n**"
                + obligation.value
                + "** "
                + _(ctx, "for")
                + " "
                + obligation.translate(ctx)
            )
        return list

    def translate(self, ctx) -> str:
        """Translate obligation

        Args:
            ctx: Translation context

        Returns:
            Translated human-readable obligation
        """
        if self == Obligation.OPTIONAL:
            return _(ctx, "Optional")
        elif self == Obligation.COMPULSORY_OPTIONAL:
            return _(ctx, "Compulsory - optional")
        elif self == Obligation.COMPULSORY:
            return _(ctx, "Compulsory")
        elif self == Obligation.OTHER:
            return _(ctx, "Other")
        elif self == Obligation.RECOMMENDED:
            return _(ctx, "Recommended")
        elif self == Obligation.OPTIONAL_SPECIALIZED:
            return _(ctx, "Optional - specialized")
        else:
            return "-"


class SubjectProgram(database.base):
    """Table used for linking subject with program.

    Combination of subject, program, year and obligation
    is used as primary key and therefor must be unique.
    """

    __tablename__ = "school_dataset_subject_program"

    subject_idx = Column(
        ForeignKey("school_dataset_subject.idx", ondelete="CASCADE"),
        primary_key=True,
    )
    program_idx = Column(
        ForeignKey("school_dataset_program.idx", ondelete="CASCADE"),
        primary_key=True,
    )
    year = Column(Integer, primary_key=True)
    obligation = Column(Enum(Obligation), primary_key=True)
    subject = relationship("Subject", back_populates="programs")
    program = relationship("Program", back_populates="subjects")

    @staticmethod
    def get(
        subject: Subject, program: Program, year: int, obligation: Obligation
    ) -> Optional[SubjectProgram]:
        """Get relation between program and subject based on year and obligation.

        Args:
            subject: Subject in relation
            program: Program in relation
            year: Year of relation
            obligation: Obligation of realtion

        Returns:
            SubjectProgram if relation exists, None otherwise.
        """
        query = (
            session.query(SubjectProgram)
            .filter_by(subject_idx=subject.idx)
            .filter_by(program_idx=program.idx)
            .filter_by(year=year)
            .filter_by(obligation=obligation)
            .one_or_none()
        )

        return query

    @staticmethod
    def add(
        subject: Subject, program: Program, year: int, obligation: Obligation
    ) -> SubjectProgram:
        """Create relation between subject and program based on year and obligation

        Args:
            subject: Subject in relation
            program: Program in relation
            year: Year of relation
            obligation: Obligation of realtion

        Returns:
            Created SubjectProgram relation
        """

        relation = SubjectProgram(
            subject_idx=subject.idx,
            program_idx=program.idx,
            year=year,
            obligation=obligation,
        )

        session.add(relation)
        session.commit()

        return relation

    def delete(self):
        """Delete relation from DB."""
        session.delete(self)
        session.commit()


class Teacher(database.base):
    """Table holding data about teachers.
    Each teacher has unique constraint on schoold ID and guild ID.
    """

    __tablename__ = "school_dataset_teacher"
    __table_args__ = (
        UniqueConstraint("school_id", "guild_id", name="school_id_guild_id_unique"),
    )

    idx = Column(Integer, primary_key=True)
    school_id = Column(Integer)
    guild_id = Column(BigInteger)
    name = Column(String)
    modified_time = Column(DateTime, server_default=func.now(), onupdate=func.now())
    subjects = relationship(
        "Subject",
        secondary=teachers_subjects,
        back_populates="teachers",
    )
    guaranted_subjects = relationship(
        "Subject",
        back_populates="guarantor",
    )

    _used_filter_generators = []
    _is_used_checks = []

    @staticmethod
    def add_used_filter_generator(func: Callable):
        """Add callable to list of functions which are called
        to get filter of used teacher.

        The function must return filter statement, for example:

        `stmt = exists().where(Teacher.idx==MyDatabaseObject.foreign_teacher_id)`

        """
        if func is None:
            return

        if func not in Teacher._used_filter_generators:
            Teacher._used_filter_generators.append(func)

    @staticmethod
    def add_is_used_check(func: Callable):
        """Add callable to list of functions which are called
        to check if teacher is in use somewhere.

        The function must return bool.
        """
        if func is None:
            return

        if func not in Teacher._is_used_checks:
            Teacher._is_used_checks.append(func)

    @staticmethod
    def get(ctx, school_id: int = None, name: str = None) -> List[Teacher]:
        """Get list of Teachers searched by arguments.

        Args:
            ctx: Context, used to specify guild
            name: Teacher name

        Returns:
            List of Teachers

        """
        query = session.query(Teacher).filter_by(guild_id=ctx.guild.id)

        if school_id:
            query = query.filter_by(school_id=school_id)

        if name:
            query = query.filter(Teacher.name.ilike(f"%{name}%"))

        return query.all()

    @staticmethod
    def add(ctx, school_id: int, name: str) -> Teacher:
        """Add new teacher to database. If teacher exists,
        edits teacher name.

        Args:
            ctx: Context, used to specify guild
            name: Teacher name

        Returns:
            Created or updated Teacher
        """

        teacher = (
            session.query(Teacher)
            .filter_by(school_id=school_id, guild_id=ctx.guild.id)
            .one_or_none()
        )

        if not teacher:
            teacher = Teacher(school_id=school_id, guild_id=ctx.guild.id)

        teacher.name = name

        session.merge(teacher)
        session.commit()

        return teacher

    @staticmethod
    def purge(ctx):
        """BEWARE! Purges all teachers that are not used!"""

        query = session.query(Teacher).filter_by(guild_id=ctx.guild.id)

        for function in Teacher._used_filter_generators:
            query = query.filter(not_(function()))

        query.delete(synchronize_session="fetch")

        session.commit()

    @staticmethod
    def get_not_used(ctx) -> List[Teacher]:
        """Returns list of teachers that are not used.

        Args
            ctx: Context used to get guild ID

        Returns:
            List of unused teachers based on filter generators.
        """
        query = session.query(Teacher).filter_by(guild_id=ctx.guild.id)

        for function in Teacher._used_filter_generators:
            query = query.filter(not_(function()))

        return query.all()

    def save(self):
        """Save Teacher object after editing."""
        session.commit()

    def is_used(self) -> bool:
        """Checks if teacher is used based on registered check functions.

        Returns:
            True if tacher is used, False if not."""
        for function in Teacher._is_used_checks:
            if function(self):
                return True

        return False

    def delete(self):
        """Delete Teacher from DB."""
        session.delete(self)
        session.commit()

    def __repr__(self) -> str:
        return (
            f'<{self.__class__.__name__} idx="{self.idx}" school_id="{self.school_id}"'
            f'guild_id="{self.guild_id}" name="{self.name}">'
        )

    def dump(self) -> dict:
        return {
            "idx": self.id,
            "schoold_id": self.school_id,
            "guild_id": self.guild_id,
            "name": self.name,
            "subjects": self.subjects,
        }


class Program(database.base):
    """Table used to hold program information.
    Eeach program is unique based on guild, abbreviaton
    and degree.

    """

    __tablename__ = "school_dataset_program"
    __table_args__ = (
        UniqueConstraint(
            "guild_id",
            "abbreviation",
            "degree",
            name="guild_id_abbreviation_degree_unique",
        ),
    )

    idx = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger)
    abbreviation = Column(String)
    name = Column(String)
    degree = Column(Enum(Degree))
    language = Column(String)
    type = Column(Enum(ProgramType))
    modified_time = Column(DateTime, server_default=func.now(), onupdate=func.now())
    subjects = relationship(
        "SubjectProgram",
        back_populates="program",
        cascade="all, delete-orphan, delete",
    )

    @staticmethod
    def get(ctx, degree: Degree = None, abbreviation: str = None) -> List[Program]:
        """Get list of programs based on arguments.

        Args:
            ctx: Context used to determine guild
            degree: Optional argument to filter
            abbreviation: Optional argument to filter

        Returns:
            List of found programs.
        """
        query = session.query(Program).filter_by(guild_id=ctx.guild.id)

        if degree:
            query = query.filter_by(degree=degree)

        if abbreviation:
            query = query.filter_by(abbreviation=abbreviation)

        return query.all()

    def save(self):
        """Save program after editing"""
        session.commit()

    def add(ctx, abbreviation: str, degree: Degree) -> Program:
        """Add or edit program if exists

        Args:
            abbreviation: Program abbreviation
            degree: Program degree

        Returns:
            Created or edited program.
        """
        query = (
            session.query(Program)
            .filter_by(guild_id=ctx.guild.id, abbreviation=abbreviation, degree=degree)
            .one_or_none()
        )

        if query:
            return query

        program = Program(
            guild_id=ctx.guild.id, abbreviation=abbreviation, degree=degree
        )

        session.add(program)
        session.commit()

        return program

    def delete(self):
        """Delete program."""
        session.delete(self)
        session.commit()

    def __repr__(self) -> str:
        return (
            f'<{self.__class__.__name__} idx="{self.idx}" guild_id="{self.guild_id}" '
            f'abbreviation="{self.abbreviation}" name="{self.name}" degree="{self.degree}">'
        )

    def dump(self) -> dict:
        return {
            "idx": self.id,
            "guild_id": self.guild_id,
            "abbreviation": self.abbreviation,
            "name": self.name,
            "degree": self.degree,
            "subjects": self.subjects,
        }


class SubjectUrl(database.base):
    """Table holding list of subjects URL"""

    __tablename__ = "school_dataset_subject_url"

    subject_id = Column(
        Integer,
        ForeignKey("school_dataset_subject.idx", ondelete="CASCADE"),
        primary_key=True,
    )
    url = Column(String, primary_key=True)
    subject = relationship("Subject", back_populates="url")

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} subject_ixd="{self.subject_ixd}" url="{self.url}">'

    def dump(self) -> dict:
        return {
            "subject_ixd": self.subject_ixd,
            "url": self.url,
        }


class Subject(database.base):
    """Table used to hold subject data.
    Subject abbreviation must be unique for each guild.
    """

    __tablename__ = "school_dataset_subject"
    __table_args__ = (
        UniqueConstraint(
            "abbreviation", "guild_id", name="abbreviation_guild_id_unique"
        ),
    )

    idx = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger)
    abbreviation = Column(String)
    name = Column(String)
    institute = Column(String)
    semester = Column(Enum(Semester))
    guarantor_id = Column(
        Integer, ForeignKey("school_dataset_teacher.idx", ondelete="SET NULL")
    )
    guarantor = relationship(
        lambda: Teacher,
        back_populates="guaranted_subjects",
    )
    teachers = relationship(
        lambda: Teacher,
        secondary=teachers_subjects,
        back_populates="subjects",
    )
    modified_time = Column(DateTime, server_default=func.now(), onupdate=func.now())
    programs = relationship(
        "SubjectProgram", back_populates="subject", cascade="all, delete-orphan, delete"
    )
    url = relationship(
        "SubjectUrl", back_populates="subject", cascade="all, delete-orphan, delete"
    )

    _used_filter_generators = []
    _is_used_checks = []

    @staticmethod
    def add_used_filter_generator(func: Callable):
        """Add callable to list of functions which are called
        to get filter of used subjects.

        The function must return filter statement, for example:

        `stmt = exists().where(Subject.idx==MyDatabaseObject.foreign_teacher_id)`

        """
        if func is None:
            return

        if func not in Subject._used_filter_generators:
            Subject._used_filter_generators.append(func)

    @staticmethod
    def add_is_used_check(func: Callable):
        """Add callable to list of functions which are called
        to check if subject is in use somewhere.

        The function must return bool.
        """
        if func is None:
            return

        if func not in Subject._is_used_checks:
            Subject._is_used_checks.append(func)

    @staticmethod
    def get_not_used(ctx) -> List[Subject]:
        """Get list of non-used subjects based on check function list.

        Args:
            ctx: Context used to determine guild.

        Returns:
            List of non-used subjects.
        """
        query = session.query(Subject).filter_by(guild_id=ctx.guild.id)

        for function in Subject._used_filter_generators:
            query = query.filter(not_(function()))

        return query.all()

    @staticmethod
    def purge(ctx):
        """BEWARE! Purges all subjects that are not used!

        Args:
            ctx: Context used to determine guild.
        """

        query = session.query(Subject).filter_by(guild_id=ctx.guild.id)

        for function in Subject._used_filter_generators:
            query = query.filter(not_(function()))

        query.delete(synchronize_session="fetch")

        session.commit()

    @staticmethod
    def get(ctx, abbreviation: str = None, name: str = None) -> List[Subject]:
        """Get subjects based on arguments.

        Args:
            abbreviation: Abbreviation used to search
            name: Name of subject to search for

        Returns:
            List of subjects based on search arguments.

        """
        query = session.query(Subject).filter_by(guild_id=ctx.guild.id)

        if abbreviation:
            query = query.filter_by(abbreviation=abbreviation.upper())

        if name:
            query = query.filter(Subject.name.ilike(f"%{name}%"))

        return query.one_or_none()

    @staticmethod
    def from_json(ctx, json_data) -> Subject:
        """Create subject based on JSON data from import file.
        Update subject information if subject with same abbreviation
        exists.

        Args:
            ctx: Context used to determine guild
            json_data: Formated JSON data

        Returns:
            Created or updated Subject
        """
        abbreviation = json_data.get("abbreviation", None)

        if not abbreviation:
            return None

        subject = (
            session.query(Subject)
            .filter_by(abbreviation=abbreviation, guild_id=ctx.guild.id)
            .one_or_none()
        )

        if not subject:
            subject = Subject(
                guild_id=ctx.guild.id,
                abbreviation=abbreviation,
            )

        name = json_data.get("name", None)
        institute = json_data.get("institute", None)
        winter_semester = json_data.get("winter_semester", False)
        summer_semester = json_data.get("summer_semester", False)

        subject.semester = Semester.from_bool(winter_semester, summer_semester)

        subject.name = name
        subject.institute = institute

        session.merge(subject)
        session.flush()

        query = session.query(SubjectUrl).filter_by(subject_idx=subject.idx).all()
        for relation in query:
            session.delete(relation)

        json_url = json_data.get("link", None)

        for url_str in json_url:
            subject.url.append(SubjectUrl(subject_id=subject.idx, url=url_str))

        session.commit()

        return subject

    def is_used(self) -> bool:
        """Checks if subject is used based on check functions."""
        for function in Subject._is_used_checks:
            if function(self):
                return True

        return False

    def delete(self):
        """Delete subject."""
        session.delete(self)
        session.commit()

    def save(self):
        """Save updated subject"""
        session.commit()

    def add_teachers(self, teachers: List[Teacher]) -> List[str]:
        """Add teachers to subject.

        Args:
            teachers: List of teachers

        Returns:
            ID's of teachers that were not teaching subject.
        """
        added = []
        for teacher in teachers:
            if teacher not in self.teachers:
                added.append(str(teacher.school_id))
                self.teachers.append(teacher)

        session.commit()

        return added

    def remove_teachers(self, teachers: List[Teacher]) -> List[str]:
        """Remove  teachers to subject.

        Args:
            teachers: List of teachers

        Returns:
            ID's of teachers that were teaching subject.
        """
        removed = []
        for teacher in teachers:
            if teacher in self.teachers:
                removed.append(str(teacher.school_id))
                self.teachers.remove(teacher)

        session.commit()

        return removed

    def import_programs(self, ctx, programs: Dict):
        """Remove all relations between subject and programs
        and create new one based on import data.

        Args:
            programs: Dict containing abbreviation, degree, year and obligation.
        """
        query = session.query(SubjectProgram).filter_by(subject_idx=self.idx).all()
        for relation in query:
            session.delete(relation)

        for program_data in programs:
            program = Program.add(
                ctx, program_data["abbreviation"], program_data["degree"]
            )
            sub_prog = SubjectProgram(
                year=program_data["year"],
                obligation=Obligation(Obligation(program_data["obligation"])),
            )
            sub_prog.program = program
            self.programs.append(sub_prog)

        session.commit()

    def __repr__(self) -> str:
        return (
            f'<{self.__class__.__name__} idx="{self.idx}" guild_id="{self.guild_id}" '
            f'abbreviation="{self.abbreviation} name="{self.name}" institute="{self.institute}" '
            f'programs="{self.programs}" semester="{self.semester}" '
            f'guarantor="{self.guarantor}" teachers="{self.teachers}" url="{self.url}">'
        )

    def dump(self) -> dict:
        return {
            "idx": self.idx,
            "guild_id": self.guild_id,
            "name": self.name,
            "institute": self.institute,
            "programs": self.programs,
            "semester": self.semester,
            "guarantor": self.guarantor,
            "teachers": self.teachers,
            "url": self.url,
        }
