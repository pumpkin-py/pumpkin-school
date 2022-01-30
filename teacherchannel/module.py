import nextcord
from nextcord.ext import tasks, commands

import pie.database.config
from pie import check, i18n, logger, utils

from .database import TeacherChannel as TeacherChannelDB

_ = i18n.Translator("modules/school").translate
guild_log = logger.Guild.logger()
config = pie.database.config.Config.get()

appendix = "_teacher"


class TeacherChannel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.load_views.start()

    @commands.guild_only()
    @commands.check(check.acl)
    @commands.group(name="teacherchannel")
    async def teacherchannel_(self, ctx):
        """Cloning and syncing teacher channels."""
        await utils.discord.send_help(ctx)

    @commands.check(check.acl)
    @teacherchannel_.command(name="list")
    async def teacherchannel_list(self, ctx):
        """List active teacher channels."""

        class Item:
            def __init__(self, obj: TeacherChannelDB):
                channel_o = ctx.guild.get_channel(obj.o_channel_id)
                channel_t = ctx.guild.get_channel(obj.t_channel_id)
                self.o_channel = "#" + getattr(channel_o, "name", str(obj.o_channel_id))
                self.t_channel = "#" + getattr(channel_t, "name", str(obj.t_channel_id))
                self.teachers = ", ".join(
                    [
                        getattr(
                            ctx.guild.get_member(i.teacher_id),
                            "display_name",
                            str(i.teacher_id),
                        )
                        for i in obj.teachers
                    ]
                )

        items = [Item(i) for i in TeacherChannelDB.get_all(ctx.guild.id)]
        if len(items) < 1:
            await ctx.reply(_(ctx, "No teacher channels are set."))
            return
        table = utils.text.create_table(
            items,
            header={
                "o_channel": _(ctx, "Original channel"),
                "t_channel": _(ctx, "Teacher channel"),
                "teachers": _(ctx, "Teachers"),
            },
        )
        for page in table:
            await ctx.send("```" + page + "```")

    @commands.check(check.acl)
    @teacherchannel_.command(name="set")
    async def teacherchannel_set(
        self, ctx, channel: nextcord.TextChannel, teacher: nextcord.Member
    ):
        """<channel> <teacher>
        Assign a teacher to a channel. Accepts both original channel and teacher channel as a parameter."""
        teacherchannel = TeacherChannelDB.get(ctx.guild.id, channel.id)
        if not teacherchannel:
            teacherchannel = TeacherChannelDB.get_by_t_channel(ctx.guild.id, channel.id)
        if not teacherchannel:
            newchannel = await channel.clone(name=channel.name + appendix)
            await newchannel.move(after=channel, offset=0)
            await newchannel.set_permissions(
                teacher, read_messages=True, send_messages=True
            )
            TeacherChannelDB.add(ctx.guild.id, newchannel.id, channel.id, teacher.id)
            await guild_log.info(
                ctx.author,
                ctx.channel,
                f"New teacherchannel created: <#{newchannel.id}>.",
            )
        else:
            TeacherChannelDB.add(
                teacherchannel.guild_id,
                teacherchannel.t_channel_id,
                teacherchannel.o_channel_id,
                teacher.id,
            )
            await ctx.guild.get_channel(teacherchannel.t_channel_id).set_permissions(
                teacher, read_messages=True, send_messages=True
            )
            await guild_log.info(
                ctx.author,
                ctx.channel,
                f"Teacher <@{teacher.id}> assigned to channel <#{teacherchannel.t_channel_id}>.",
            )
        await ctx.reply(_(ctx, "Teacher channel and teacher set."))

    @commands.check(check.acl)
    @teacherchannel_.command(name="unset")
    async def teacherchannel_unset(
        self, ctx, channel: nextcord.TextChannel, teacher: nextcord.Member = None
    ):
        """<channel> [teacher]
        Unset a teacher from a channel. Defaults to all teachers of that channel. Does not delete the channel."""
        teacherchannel = TeacherChannelDB.get(ctx.guild.id, channel.id)
        if not teacherchannel:
            teacherchannel = TeacherChannelDB.get_by_t_channel(ctx.guild.id, channel.id)
        if not teacherchannel:
            await ctx.reply(
                _(ctx, "Channel is not set in the database as a teacher channel.")
            )
            return
        channel = ctx.guild.get_channel(teacherchannel.t_channel_id)
        if teacher is not None:
            print(teacher)
            await channel.set_permissions(teacher, overwrite=None)
            TeacherChannelDB.remove(
                ctx.guild.id, teacherchannel.t_channel_id, teacher.id
            )
            await ctx.reply(_(ctx, "Teacher was removed."))
            await guild_log.info(
                ctx.author,
                ctx.channel,
                f"Teacher <@{teacher.id}> removed from channel <#{teacherchannel.t_channel_id}>.",
            )
        else:
            teacherDB_list = teacherchannel.teachers.copy()
            for teacherDB in teacherDB_list:
                await channel.set_permissions(
                    ctx.guild.get_member(teacherDB.teacher_id), overwrite=None
                )
                TeacherChannelDB.remove(
                    ctx.guild.id, teacherchannel.t_channel_id, teacherDB.teacher_id
                )
            await ctx.reply(_(ctx, "Teacher channel was unset, but was not deleted."))
            await guild_log.info(
                ctx.author,
                ctx.channel,
                f"Teacher channel <#{teacherchannel.t_channel_id}> is no longer a teacher channel.",
            )

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self, channel_b: nextcord.abc.GuildChannel, channel_a: nextcord.abc.GuildChannel
    ):
        if not isinstance(channel_a, nextcord.TextChannel):
            return
        teacherchannel = TeacherChannelDB.get(channel_a.guild.id, channel_a.id)
        if not teacherchannel:
            return
        if channel_a.id == teacherchannel.t_channel_id:
            return
        await self._sync(channel_b, channel_a, teacherchannel)

    @tasks.loop(seconds=10.0, count=1)
    async def load_views(self):
        guild_ids = [i.guild_id for i in TeacherChannelDB.get_guilds()]
        for guild_id in guild_ids:
            guild = self.bot.get_guild(guild_id)
            channels_to_sync = TeacherChannelDB.get_all(guild_id)
            for channel_info in channels_to_sync:
                channel_o = guild.get_channel(channel_info.o_channel_id)
                channel_t = guild.get_channel(channel_info.t_channel_id)
                if not channel_o:
                    if channel_t is not None:
                        ch_name = channel_t.name
                        await channel_t.delete()
                    else:
                        ch_name = channel_info.t_channel_id
                    await guild_log.warning(
                        None,
                        None,
                        f"Teacher channel {ch_name} cannot be synced, channel {channel_info.o_channel_id} does not exist! Deleting.",
                    )
                    TeacherChannelDB.remove(guild_id, channel_info.t_channel_id)
                channel_t = guild.get_channel(channel_info.t_channel_id)
                if not channel_t:
                    await self._recreate_ch(channel_info, channel_o)
                    return
                await self._sync(channel_t, channel_o, channel_info)

    @load_views.before_loop
    async def before_load(self):
        """Ensures that bot is ready before loading any
        persitant view.
        """
        await self.bot.wait_until_ready()

    async def _sync(
        self,
        channel_b: nextcord.abc.GuildChannel,
        channel_a: nextcord.abc.GuildChannel,
        teacherchannel: TeacherChannelDB,
    ) -> None:
        channel_t = channel_a.guild.get_channel(teacherchannel.t_channel_id)
        if not channel_t:
            await self._recreate_ch(teacherchannel, channel_a)
            return
        if channel_a.category != channel_b.category:
            await channel_t.move(category=channel_a.category, after=channel_a, offset=0)
        if channel_a.overwrites != channel_b.overwrites:
            # negative change
            for (target, overwrite) in channel_b.overwrites.items():
                if (target, overwrite) in channel_a.overwrites.items():
                    continue
                if target.id not in [i.teacher_id for i in teacherchannel.teachers]:
                    await channel_t.set_permissions(target, overwrite=None)

            # positive change
            for target, overwrite in channel_a.overwrites.items():
                if (target, overwrite) in channel_b.overwrites.items():
                    continue
                if target.id not in [i.teacher_id for i in teacherchannel.teachers]:
                    await channel_t.set_permissions(target, overwrite=overwrite)
        if channel_a.name != channel_b.name and not channel_b.name.endswith(appendix):
            await channel_t.edit(name=channel_a.name + appendix)
        if channel_a.topic != channel_b.topic:
            await channel_t.edit(topic=channel_a.topic)

    async def _recreate_ch(
        self, teacherchannel: TeacherChannelDB, channel_o: nextcord.abc.GuildChannel
    ) -> nextcord.abc.GuildChannel:
        teachers = TeacherChannelDB.get(teacherchannel.guild_id, channel_o.id).teachers
        channel_t = await channel_o.clone(name=channel_o.name + appendix)
        for teacher in teachers:
            TeacherChannelDB.remove(
                teacherchannel.guild_id, teacherchannel.t_channel_id, teacher.teacher_id
            )
            teacher_member = channel_o.guild.get_member(teacher.teacher_id)
            TeacherChannelDB.add(
                teacherchannel.guild_id, channel_t.id, channel_o.id, teacher_member.id
            )
            await channel_t.set_permissions(
                teacher_member, read_messages=True, send_messages=True
            )
        await channel_t.move(after=channel_o, offset=0)
        return channel_t


def setup(bot) -> None:
    bot.add_cog(TeacherChannel(bot))
