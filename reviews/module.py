from typing import List

import discord
from discord.ext import commands

from pie.utils.objects import ScrollableVotingEmbed, VotableEmbed
from pie import check, i18n, logger, utils

from .database import Review, Subject

_ = i18n.Translator("modules/school").translate
guild_log = logger.Guild.logger()


MAX_LEN = 1024


def _split_subjects(subjects: list[Subject]) -> list[str]:
    ans = [""]
    for subject in subjects:
        if len(ans[-1]) + len(subject.shortcut) + len(", ") > MAX_LEN:
            ans.append("")
        if ans[-1]:
            ans[-1] += ", "
        ans[-1] += subject.shortcut
    return ans


def _split_review(review: str) -> List[str]:
    """Splits the review into chunks that can fit into an embed."""
    ans = []
    number_of_full_chunks = len(review) // MAX_LEN
    for i in range(number_of_full_chunks):
        start_index = i * MAX_LEN
        ans.append(review[start_index : start_index + MAX_LEN])
    if len(review) % MAX_LEN:
        # Add the last non-full chunk
        ans.append(review[number_of_full_chunks * MAX_LEN :])
    return ans


class ReviewEmbed(VotableEmbed):
    def __init__(
        self, review_id: int, ctx: discord.ext.commands.Context, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.review_id: int = review_id
        self.ctx: discord.ext.commands.Context = ctx

        self.__set_voting_footer(Review.get(self.review_id))

    async def _refresh_votes(self, interaction):
        review = Review.get(self.review_id)
        if not review:
            # This review has been removed in the meantime
            return
        self.__set_voting_footer(review)
        await interaction.response.edit_message(embed=self)

    def __set_voting_footer(self, review: Review):
        self.set_footer(
            text=f"👍: {review.get_positive_votes()}, 👎: {review.get_negative_votes()}"
        )

    async def vote_up(self, interaction: discord.Interaction):
        review = Review.get(self.review_id)
        print(review)
        if not review:
            # This review has been removed in the meantime
            return
        review.vote_up(interaction.user)
        await self._refresh_votes(interaction)

    async def vote_down(self, interaction: discord.Interaction):
        review = Review.get(self.review_id)
        if not review:
            # This review has been removed in the meantime
            return
        review.vote_down(interaction.user)
        await self._refresh_votes(interaction)

    async def vote_neutral(self, interaction: discord.Interaction):
        review = Review.get(self.review_id)
        if not review:
            # This review has been removed in the meantime
            return
        review.vote_neutral(interaction.user)
        await self._refresh_votes(interaction)


class Reviews(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @check.acl2(check.ACLevel.MEMBER)
    @commands.guild_only()
    @commands.group(name="review")
    async def review(self, ctx):
        """Manage your subject reviews."""
        await utils.discord.send_help(ctx)

    @check.acl2(check.ACLevel.MEMBER)
    @commands.guild_only()
    @review.command(name="subject", aliases=["see"])
    async def review_subject(self, ctx: discord.ext.commands.Context, subject: str):
        """See subject's reviews. Search subject by abbreviations."""
        db_subject = Subject.get(ctx.guild, subject)
        if db_subject is None:
            return await ctx.reply(
                _(ctx, "Subject {subject} not found.").format(subject=subject)
            )

        db_reviews: List[Review] = sorted(
            list(db_subject.reviews), key=lambda x: x.date, reverse=True
        )

        subject_abbr = db_subject.shortcut
        if db_subject.category:
            subject_abbr += f" ({db_subject.category})"

        if len(db_reviews) == 0:
            return await ctx.reply(_(ctx, "Subject has no reviews yet."))

        average_review = sum(db_review.tier for db_review in db_reviews) / len(
            db_reviews
        )

        embeds: List[ReviewEmbed] = []
        for db_review in db_reviews:
            embed = ReviewEmbed(db_review.id, ctx)
            embed.title = subject_abbr
            embed.add_field(name=_(ctx, "Name"), value=db_subject.name)
            embed.add_field(name=_(ctx, "Average rating"), value=average_review)
            embed.add_field(
                name=_(ctx, "Review author"),
                value=_(ctx, "Anonymous user")
                if db_review.anonym
                else getattr(
                    ctx.guild.get_member(db_review.discord_id),
                    "display_name",
                    _(ctx, "Unknown user"),
                ),
                inline=False,
            )
            embed.add_field(name=_(ctx, "Rating"), value=db_review.tier)
            embed.add_field(
                name=_(ctx, "Date"), value=db_review.date.strftime(_(ctx, "%b %d %Y"))
            )

            review_chunks: List[str] = _split_review(db_review.text_review)
            if len(review_chunks):
                embed.add_field(
                    name=_(ctx, "Text review"), value=review_chunks[0], inline=False
                )
                for chunk in review_chunks[1:]:
                    embed.add_field(name="", value=chunk)
            embeds.append(embed)
        await ScrollableVotingEmbed(ctx, embeds).scroll()

    @check.acl2(check.ACLevel.MEMBER)
    @commands.guild_only()
    @review.command(name="list", aliases=["available"])
    async def review_list(self, ctx: discord.ext.commands.Context):
        """Get list of reviewed subjects"""
        subjects = Subject.get_reviewed(ctx.guild)
        if len(subjects) == 0:
            await ctx.reply(_(ctx, "There are no rated subjects yet."))
            return
        embed = discord.Embed(title=_(ctx, "Available subjects"))
        for subject_substring in _split_subjects(subjects):
            embed.add_field(name="", value=subject_substring)
        await ctx.reply(embed=embed)

    @check.acl2(check.ACLevel.MEMBER)
    @commands.guild_only()
    @review.command(name="my-list")
    async def review_my_list(self, ctx: discord.ext.commands.Context):
        """Get list of your reviewed subjects."""
        subjects = Subject.get_reviewed_by_user(ctx.guild, ctx.author)
        if len(subjects) == 0:
            return await ctx.reply(_(ctx, "You have not rated any subject yet."))
        embed = discord.Embed(title=_(ctx, "My rated subjects"))
        for subject_substring in _split_subjects(subjects):
            embed.add_field(name="", value=subject_substring)
        await ctx.reply(embed=embed)

    @staticmethod
    async def _add_review(
        ctx: discord.ext.commands.Context,
        subject: str,
        mark: int,
        text: str,
        anonymous: bool,
    ):
        """Add and return review"""
        if mark < 1 or mark > 5:
            await ctx.reply(_(ctx, "Mark must be in the range <1, 5>."))
            return None

        # check if subject is in database
        db_subject = Subject.get(ctx.guild, subject)
        if db_subject is None:
            await ctx.reply(_(ctx, "Unknown subject."))
            return None

        if text is None or not len(text):
            await ctx.reply(_(ctx, "Please provide text for the review."))
            return None

        result = Review.add(ctx.guild, ctx.author, subject, mark, anonymous, text)
        return result

    @check.acl2(check.ACLevel.MEMBER)
    @commands.guild_only()
    @review.command(name="add", aliases=["update"])
    async def review_add(
        self,
        ctx: discord.ext.commands.Context,
        subject: str = None,
        mark: int = None,
        *,
        text: str = "",
    ):
        """Add a review

        subject: Subject code
        mark: 1-5 (one being best)
        text: Your review
        """
        if not subject or not mark:
            await utils.discord.send_help(ctx)
            return
        result = await self._add_review(ctx, subject, mark, text, False)
        if result is not None:
            await guild_log.info(
                ctx.author, ctx.channel, f"Added/updated review for subject {subject}."
            )
            await ctx.reply(_(ctx, "Review successfully added."))

    @check.acl2(check.ACLevel.MEMBER)
    @commands.guild_only()
    @review.command(name="add-anonymous", aliases=["anonymous", "anon"])
    async def review_add_anonymous(
        self,
        ctx: discord.ext.commands.Context,
        subject: str = None,
        mark: int = None,
        *,
        text: str = "",
    ):
        """Adds an anonymous review and deletes your message.

        subject: Subject code
        mark: 1-5 (one being best)
        text: Your review
        """
        if not subject or not mark:
            await utils.discord.send_help(ctx)
            return
        result = await self._add_review(ctx, subject, mark, text, True)
        if result is not None:
            await guild_log.info(
                ctx.author,
                ctx.channel,
                f"Added anonymous review for subject {subject}.",
            )
            await ctx.send(_(ctx, "Anonymous review successfully added."))
        await ctx.message.delete()

    @check.acl2(check.ACLevel.MEMBER)
    @commands.guild_only()
    @review.command(name="remove", aliases=["delete"])
    async def review_remove(self, ctx: discord.ext.commands.Context, subject: str):
        """Remove your review

        subject: Subject abbreviation
        """
        if Review.remove(ctx.guild, ctx.author, subject):
            await guild_log.info(
                ctx.author, ctx.channel, f"Removed their review for subject {subject}."
            )
            await ctx.reply(_(ctx, "Review deleted successfully."))
            return
        await ctx.reply(_(ctx, "Review for this subject not found."))

    @check.acl2(check.ACLevel.SUBMOD)
    @commands.guild_only()
    @review.command(name="sudo-remove", aliases=["sudo-rm", "sudo-delete"])
    async def sudo_review_remove(
        self, ctx: discord.ext.commands.Context, abbreviation: str, user: discord.User
    ):
        """Remove other user's reviews."""
        if Review.remove(ctx.guild, user, abbreviation):
            await ctx.reply(
                _(
                    ctx,
                    "Review on subject {abbreviation} from user {username} removed.",
                ).format(abbreviation=abbreviation, username=user.display_name)
            )
            await guild_log.info(
                ctx.author,
                ctx.channel,
                f"Removed review on subject {abbreviation} from user {user.display_name} ({user.id}).",
            )
            return
        await ctx.reply(_(ctx, "Review not found."))

    @check.acl2(check.ACLevel.MEMBER)
    @commands.guild_only()
    @commands.group(name="subject")
    async def subject(self, ctx):
        """Manage subjects."""
        await utils.discord.send_help(ctx)

    @check.acl2(check.ACLevel.MEMBER)
    @commands.guild_only()
    @subject.command(name="info")
    async def subject_info(self, ctx: discord.ext.commands.Context, abbreviation: str):
        """Get information about subject

        abbreviation: Subject code
        """
        subject = Subject.get(ctx.guild, abbreviation)
        if subject is None:
            return await ctx.reply(_(ctx, "Unknown subject."))

        embed = discord.Embed(title=subject.shortcut)
        embed.add_field(name=_(ctx, "Name"), value=subject.name)
        embed.add_field(name=_(ctx, "Department"), value=subject.category)
        embed.add_field(
            name=_(ctx, "Number of reviews"), value=len(list(subject.reviews))
        )

        await ctx.reply(embed=embed)

    @check.acl2(check.ACLevel.MOD)
    @commands.guild_only()
    @subject.command(name="add", aliases=["update"])
    async def subject_add(
        self,
        ctx: discord.ext.commands.Context,
        abbreviation: str,
        name: str,
        category: str,
    ):
        """
        Add a subject.
        abbreviation is a subject code,
        name is its full name
        and category is its department
        """
        Subject.add(ctx.guild, abbreviation, name, category)
        await guild_log.info(
            ctx.author, ctx.channel, f"Added/updated subject: {abbreviation}."
        )
        await ctx.reply(_(ctx, "Subject added."))

    @check.acl2(check.ACLevel.MOD)
    @commands.guild_only()
    @subject.command(name="remove", aliases=["delete"])
    async def subject_remove(
        self, ctx: discord.ext.commands.Context, abbreviation: str
    ):
        """Remove a subject."""
        if Subject.remove(ctx.guild, abbreviation):
            await guild_log.info(
                ctx.author, ctx.channel, f"Removed subject: {abbreviation}."
            )
            return await ctx.reply(_(ctx, "Subject removed."))
        await ctx.reply(_(ctx, "Subject not found."))


async def setup(bot) -> None:
    await bot.add_cog(Reviews(bot))
