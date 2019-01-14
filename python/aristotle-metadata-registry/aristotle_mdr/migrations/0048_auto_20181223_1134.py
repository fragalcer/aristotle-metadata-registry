# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2018-12-23 17:34
from __future__ import unicode_literals

import autoslug.fields
from django.db import migrations, models
import django.db.models.deletion

from aristotle_mdr.utils.migrations import (
    classproperty,
    StewardMigration
)


class Migration(StewardMigration):

    dependencies = [
        ('aristotle_mdr', '0047_auto_20181217_0926'),
    ]

    @classproperty
    def operations(cls):
        return [
            migrations.RunPython(cls.add_stewardship_org, migrations.RunPython.noop),
            migrations.RunPython(cls.fetch_stewardship_org_uuid, migrations.RunPython.noop),
            migrations.RunPython(
                lambda a, s: cls.assign_orgs_to_model(a,s, "registrationauthority"),
                migrations.RunPython.noop
            ),
            migrations.RunPython(
                lambda a, s: cls.assign_orgs_to_model(a,s, "workgroup"),
                migrations.RunPython.noop
            ),
            migrations.RunPython(
                lambda a, s: cls.assign_orgs_to_model(a,s, "measure"),
                migrations.RunPython.noop
            ),
            migrations.RunPython(cls.assign_orgs_to_metadata, migrations.RunPython.noop),
        ]
