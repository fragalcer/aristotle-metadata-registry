from django.test import TestCase, tag
from django.conf import settings

import aristotle_mdr.models as models
import aristotle_mdr.perms as perms
import aristotle_mdr.tests.utils as utils
from aristotle_mdr.contrib.identifiers import models as ident_models
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.management import call_command
from reversion import revisions as reversion
from aristotle_mdr.forms.search import get_permission_sqs

import datetime
from django.utils import timezone

import string
import random

import unittest


@tag('search')
class TestSearch(utils.AristotleTestUtils, TestCase):
    @reversion.create_revision()
    def setUp(self):
        call_command('clear_index', interactive=False, verbosity=0)
        super().setUp()
        import haystack
        haystack.connections.reload('default')

        self.steward_org = models.StewardOrganisation.objects.create(name="Test SO")
        self.ra = models.RegistrationAuthority.objects.create(name="Kelly Act",
                                                              stewardship_organisation=self.steward_org)
        self.ra1 = models.RegistrationAuthority.objects.create(name="Superhuman Registration Act",
                                                               stewardship_organisation=self.steward_org)
        # Anti-registration!
        self.registrar = get_user_model().objects.create_user('william.styker@weaponx.mil','mutantsMustDie')
        self.ra.giveRoleToUser('registrar',self.registrar)
        self.assertTrue(perms.user_is_registrar(self.registrar,self.ra))
        xmen = "professorX cyclops iceman angel beast phoenix wolverine storm nightcrawler"

        self.xmen_wg = models.Workgroup.objects.create(name="X Men", stewardship_organisation=self.steward_org)
        # self.xmen_wg.registrationAuthorities.add(self.ra)
        self.xmen_wg.save()
        self.item_xmen = [
            models.ObjectClass.objects.create(name=t,definition="known xman",workgroup=self.xmen_wg)\
            for t in xmen.split()]

        for item in self.item_xmen:
            registered = self.ra.register(item,models.STATES.standard,self.su)
            self.assertTrue(item in registered['success'])
            item = models._concept.objects.get(pk=item.pk).item # Stupid cache
            self.assertTrue(item.is_public())


        avengers = "thor spiderman ironman hulk captainAmerica"

        self.avengers_wg = models.Workgroup.objects.create(name="Avengers", stewardship_organisation=self.steward_org)
        # self.avengers_wg.registrationAuthorities.add(self.ra1)
        self.item_avengers = [
            models.ObjectClass.objects.create(name=t,workgroup=self.avengers_wg)
            for t in avengers.split()]


    def test_search_factory_fails_with_bad_queryset(self):
        from django.core.exceptions import ImproperlyConfigured

        with self.assertRaises(ImproperlyConfigured):
            self.client.get(reverse('fail_search')+"?q=wolverine")

    def test_empty_search_loads(self):
        self.logout()
        response = self.client.get(reverse('aristotle:search'))
        self.assertEqual(response.status_code, 200)

    def test_one_result_search_doesnt_have_did_you_mean(self):
        self.logout()
        response = self.client.get(reverse('aristotle:search')+"?q=wolverine")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page'].object_list), 1)
        self.assertNotContains(response, "Did you mean")
        self.assertContains(response, "wolverine")

    def test_empty_search(self):
        self.logout()
        response = self.client.get(reverse('aristotle:search')+"?q=")
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.context['page'].object_list),0)

    def test_search_delete_signal(self):
        self.login_superuser()
        with reversion.create_revision():
            cable = models.ObjectClass.objects.create(name="cable",definition="known xman",workgroup=self.xmen_wg)
            self.ra.register(cable,models.STATES.standard,self.su)
            cable.save()
        self.assertTrue(cable.is_public())
        response = self.client.get(reverse('aristotle:search')+"?q=cable")
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.context['page'].object_list),1)
        with reversion.create_revision():
            cable.delete()
        response = self.client.get(reverse('aristotle:search')+"?q=cable")
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.context['page'].object_list),0)

    def test_public_search(self):
        self.logout()
        response = self.client.get(reverse('aristotle:search')+"?q=xman")
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.context['page'].object_list),len(self.item_xmen))
        for i in response.context['page'].object_list:
            self.assertTrue(i.object.is_public())

    def test_public_search_of_discussions(self):
        # Public searchers should not be able to see discussions
        self.logout()

        discussion_post_1 = models.DiscussionPost.objects.create(title="Hello World", workgroup=self.xmen_wg)
        discussion_post_2 = models.DiscussionPost.objects.create(title="Test test", workgroup=self.xmen_wg)

        response = self.client.get(reverse('aristotle:search') + "?q=hello")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page'].object_list), 0)


    def test_public_search_has_valid_facets(self):
        self.logout()
        response = self.client.get(reverse('aristotle:search')+"?q=xman")
        self.assertEqual(response.status_code,200)
        facets = response.context['form'].facets['fields']
        self.assertTrue('workgroup' not in facets.keys())
        self.assertTrue('restriction' not in facets.keys())

        self.assertTrue('facet_model_ct' in facets.keys())
        self.assertTrue('statuses' in facets.keys())

        for state, count in facets['statuses']:
            self.assertTrue(int(state) >= self.ra.public_state)


    @unittest.skipIf('WhooshEngine' in settings.HAYSTACK_CONNECTIONS['default']['ENGINE'],
                     "Whoosh doesn't support faceting")
    def test_registrar_search_has_valid_facets(self):
        response = self.client.post(reverse('friendly_login'),
                    {'username': 'william.styker@weaponx.mil', 'password': 'mutantsMustDie'})

        self.assertEqual(response.status_code,302) # logged in

        response = self.client.get(reverse('aristotle:search')+"?q=xman")
        self.assertEqual(response.status_code,200)
        facets = response.context['form'].facets['fields']
        self.assertTrue('workgroup' in facets.keys())
        self.assertTrue('restriction' in facets.keys())

        self.assertTrue('facet_model_ct' in facets.keys())
        self.assertTrue('statuses' in facets.keys())

    def test_registrar_favourite_in_list(self):
        self.logout()

        response = self.client.get(reverse('aristotle:search')+"?q=xman")
        self.assertNotContains(response, 'Add Favourite')

        response = self.client.post(reverse('friendly_login'),
                    {'username': 'william.styker@weaponx.mil', 'password': 'mutantsMustDie'})

        self.assertEqual(response.status_code,302) # logged in

        response = self.client.get(reverse('aristotle:search')+"?q=xman")
        self.assertNotContains(response, 'This item is in your favourites list')

        i = self.xmen_wg.items.first()

        self.favourite_item(self.registrar, i)
        self.assertTrue(i in self.registrar.profile.favourites.all())

        response = self.client.get(reverse('aristotle:search')+"?q=xman")
        self.assertContains(response, 'This item is in your favourites list')

    def test_registrar_search_after_adding_new_status_request(self):
        self.logout()
        response = self.client.post(reverse('friendly_login'),
                    {'username': 'william.styker@weaponx.mil', 'password': 'mutantsMustDie'})

        steve_rogers = models.ObjectClass.objects.get(name="captainAmerica")
        self.assertFalse(perms.user_can_view(self.registrar,steve_rogers))

        with reversion.create_revision():
            steve_rogers.save()

        self.make_review_request(steve_rogers, self.registrar)

        self.assertTrue(perms.user_can_view(self.registrar,steve_rogers))

        response = self.client.get(reverse('aristotle:search')+"?q=captainAmerica")
        self.assertEqual(len(response.context['page'].object_list),1)
        self.assertEqual(response.context['page'].object_list[0].object.item,steve_rogers)
        self.assertTrue(perms.user_can_view(self.registrar,response.context['page'].object_list[0].object))

    def test_workgroup_member_search(self):
        self.logout()
        # Create user model
        self.viewer = get_user_model().objects.create_user('charles@schoolforgiftedyoungsters.edu','equalRightsForAll')
        self.weaponx_wg = models.Workgroup.objects.create(name="WeaponX", stewardship_organisation=self.steward_org)

        response = self.client.post(reverse('friendly_login'),
                    {'username': 'charles@schoolforgiftedyoungsters.edu', 'password': 'equalRightsForAll'})

        self.assertEqual(response.status_code,302) # logged in

        # Charles is not in any workgroups
        self.assertFalse(perms.user_in_workgroup(self.viewer,self.xmen_wg))
        self.assertFalse(perms.user_in_workgroup(self.viewer,self.weaponx_wg))

        # Create Deadpool in Weapon X workgroup
        with reversion.create_revision():
            dp = models.ObjectClass.objects.create(name="deadpool",
                    definition="not really an xman, no matter how much he tries",
                    workgroup=self.weaponx_wg)
        dp = models.ObjectClass.objects.get(pk=dp.pk) # Un-cache
        self.assertFalse(perms.user_can_view(self.viewer,dp))
        self.assertFalse(dp.is_public())

        # Charles isn't a viewer of X-men yet, so no results.
        psqs = get_permission_sqs()
        psqs = psqs.auto_query('deadpool').apply_permission_checks(self.viewer)
        self.assertEqual(len(psqs),0)
        #response = self.client.get(reverse('aristotle:search')+"?q=deadpool")
        #self.assertEqual(len(response.context['page'].object_list),0)

        # Make viewer of XMen
        self.xmen_wg.giveRoleToUser('viewer',self.viewer)
        self.assertFalse(perms.user_can_view(self.viewer,dp))

        # Deadpool isn't an Xman yet, still no results.
        psqs = get_permission_sqs()
        psqs = psqs.auto_query('deadpool').apply_permission_checks(self.viewer)
        self.assertEqual(len(psqs),0)

        with reversion.create_revision():
            dp.workgroup = self.xmen_wg
            dp.save()
        dp = models.ObjectClass.objects.get(pk=dp.pk) # Un-cache

        # Charles is a viewer, Deadpool is in X-men, should have results now.
        psqs = get_permission_sqs()
        psqs = psqs.auto_query('deadpool').apply_permission_checks(self.viewer)
        self.assertEqual(len(psqs),1)

        response = self.client.get(reverse('aristotle:search')+"?q=deadpool")
        self.assertTrue(perms.user_can_view(self.viewer,dp))
        self.assertEqual(len(response.context['page'].object_list),1)
        self.assertEqual(response.context['page'].object_list[0].object.item,dp)

        # Take away Charles viewing rights and no results again.
        self.xmen_wg.removeRoleFromUser('viewer',self.viewer)
        psqs = get_permission_sqs()
        psqs = psqs.auto_query('deadpool').apply_permission_checks(self.viewer)
        self.assertEqual(len(psqs),0)

        response = self.client.get(reverse('aristotle:search')+"?q=deadpool")
        self.assertEqual(len(response.context['page'].object_list),0)

    def test_workgroup_member_search_of_discussions(self):
        self.logout()

        # Only workgroup members should be able to see discussion posts
        self.discussionPost = models.DiscussionPost.objects.create(title="Hello World", body="Text text",
                                                                   workgroup=self.wg1)
        # Remove viewer from workgroup
        self.wg1.removeUser(self.viewer)

        # Check that the viewer was successfully removed
        self.assertFalse(perms.user_in_workgroup(self.viewer, self.wg1))

        # Confirm discussion in QuerySet
        from haystack.query import SearchQuerySet
        sqs = SearchQuerySet()
        self.assertEqual(len(sqs.auto_query('Hello')), 1)

        # User is not in workgroup, so there should be no results
        psqs = get_permission_sqs().auto_query('Hello').apply_permission_checks(self.viewer)
        self.assertEqual(len(psqs), 0)

        # Put the viewer in the correct workgroup
        self.wg1.giveRoleToUser('manager', self.viewer)
        self.assertTrue(perms.user_in_workgroup(self.viewer, self.wg1))

        # Viewer is now in workgroup, so there should be results
        psqs = get_permission_sqs().auto_query('Hello').apply_permission_checks(self.viewer)
        self.assertEqual(len(psqs), 1)

        self.login_viewer()

        response = self.client.get(reverse('aristotle:search')+"?q=Hello")
        self.assertEqual(len(response.context['page'].object_list), 1)


    @unittest.skipIf('WhooshEngine' in settings.HAYSTACK_CONNECTIONS['default']['ENGINE'],
                      "Whoosh doesn't support faceting")
    def test_workgroup_member_search_has_valid_facets(self):
        self.logout()
        self.viewer = get_user_model().objects.create_user('charles@schoolforgiftedyoungsters.edu','equalRightsForAll')
        response = self.client.post(reverse('friendly_login'),
                    {'username': 'charles@schoolforgiftedyoungsters.edu', 'password': 'equalRightsForAll'})

        self.assertEqual(response.status_code,302) # logged in

        self.xmen_wg.giveRoleToUser('viewer',self.viewer)
        self.weaponx_wg = models.Workgroup.objects.create(name="WeaponX", stewardship_organisation=self.steward_org)

        response = self.client.post(reverse('friendly_login'),
                    {'username': 'charles@schoolforgiftedyoungsters.edu', 'password': 'equalRightsForAll'})

        self.assertEqual(response.status_code,302) # logged in

        # Create Deadpool in Weapon X workgroup
        with reversion.create_revision():
            dp = models.ObjectClass.objects.create(name="deadpool",
                    definition="not really an xman, no matter how much he tries",
                    workgroup=self.weaponx_wg)
        dp = models.ObjectClass.objects.get(pk=dp.pk) # Un-cache
        self.assertFalse(perms.user_can_view(self.viewer,dp))
        self.assertFalse(dp.is_public())

        response = self.client.get(reverse('aristotle:search')+"?q=xman")
        self.assertEqual(response.status_code,200)
        facets = response.context['form'].facets['fields']
        self.assertTrue('restriction' in facets.keys())

        self.assertTrue('facet_model_ct' in facets.keys())
        self.assertTrue('statuses' in facets.keys())
        self.assertTrue('workgroup' in facets.keys())

        for wg in facets['workgroup']:
            wg = models.Workgroup.objects.get(pk=wg)
            self.assertTrue(perms.user_in_workgroup(self.viewer,wg))

    def test_current_statuses_only_in_search_results_and_index(self):
        # See issue #327
        self.logout()
        response = self.client.post(reverse('friendly_login'),
                    {'username': 'william.styker@weaponx.mil', 'password': 'mutantsMustDie'})

        # login
        self.assertEqual(response.status_code,302) # logged in
        self.assertTrue(perms.user_is_registrar(self.registrar,self.ra))

        with reversion.create_revision():
            dp = models.ObjectClass.objects.create(name="deadpool",
                    definition="not really an xman, no matter how much he tries",
                    workgroup=self.xmen_wg)

        self.make_review_request(dp, self.registrar)

        dp = models.ObjectClass.objects.get(pk=dp.pk) # Un-cache
        self.assertTrue(perms.user_can_view(self.registrar,dp))
        self.assertFalse(dp.is_public())

        self.ra.register(dp,models.STATES.incomplete,self.registrar,
            registrationDate=timezone.now()+datetime.timedelta(days=-7)
        )

        self.ra.register(dp,models.STATES.standard,self.registrar,
            registrationDate=timezone.now()+datetime.timedelta(days=-1)
        )

        response = self.client.get(reverse('aristotle:search')+"?q=deadpool")
        self.assertEqual(len(response.context['page'].object_list),1)
        dp_result = response.context['page'].object_list[0]
        self.assertTrue(dp_result.object.name=="deadpool")
        self.assertTrue(len(dp_result.statuses) == 1)

        self.assertTrue(int(dp_result.statuses[0]) == int(models.STATES.standard))

    def test_visibility_restriction_facets(self):
        # See issue #351
        self.logout()

        response = self.client.get(reverse('aristotle:search')+"?q=xman")
        self.assertNotContains(response, 'Restriction')

        response = self.client.post(reverse('friendly_login'),
                    {'username': 'william.styker@weaponx.mil', 'password': 'mutantsMustDie'})

        self.assertEqual(response.status_code,302) # logged in
        self.assertTrue(perms.user_is_registrar(self.registrar,self.ra))

        with reversion.create_revision():
            dp = models.ObjectClass.objects.create(name="deadpool",
                    definition="not really an xman, no matter how much he tries",
                    workgroup=self.xmen_wg)

        self.make_review_request(dp, self.registrar)

        dp = models.ObjectClass.objects.get(pk=dp.pk) # Un-cache
        self.assertTrue(perms.user_can_view(self.registrar,dp))
        self.assertFalse(dp.is_public())

        self.ra.register(dp,models.STATES.candidate,self.registrar,
            registrationDate=timezone.now()+datetime.timedelta(days=-7)
        )

        response = self.client.get(reverse('aristotle:search')+"?q=xman")
        self.assertContains(response, 'Restriction')


        response = self.client.get(reverse('aristotle:search')+"?q=xman&res=1")
        self.assertNotContains(response, 'Restriction')

        self.assertContains(response, 'Item visibility state is Locked')

        self.assertEqual(len(response.context['page'].object_list),1)
        dp_result = response.context['page'].object_list[0]
        self.assertTrue(dp_result.object.name=="deadpool")
        self.assertTrue(len(dp_result.statuses) == 1)
        self.assertTrue(dp_result.object.is_locked())
        self.assertFalse(dp_result.object.is_public())

        self.assertTrue(int(dp_result.statuses[0]) == int(models.STATES.candidate))

    def test_user_can_search_own_content(self):
        self.logout()
        self.login_regular_user()
        response = self.client.get(reverse('aristotle:search')+"?q=pokemon")
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.context['page'].object_list),0)

        # Create object class
        models.ObjectClass.objects.create(
            name='pokemon',
            definition='Pocket Monsters',
            submitter=self.regular
        )

        response = self.client.get(reverse('aristotle:search')+"?q=pokemon")
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.context['page'].object_list),1)

        self.logout()
        self.login_editor()
        response = self.client.get(reverse('aristotle:search')+"?q=pokemon")
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.context['page'].object_list),0)


    def test_user_can_search_own_content_and_other_content(self):
        self.logout()
        self.login_regular_user()
        response = self.client.get(reverse('aristotle:search')+"?q=pokemon")
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.context['page'].object_list),0)

        # Create object class
        models.ObjectClass.objects.create(
            name='pokemon',
            definition='Pocket Monsters',
            submitter=self.regular
        )

        response = self.client.get(reverse('aristotle:search')+"?q=pokemon")
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.context['page'].object_list),1)

        self.logout()
        self.login_editor()
        response = self.client.get(reverse('aristotle:search')+"?q=pokemon")
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.context['page'].object_list),0)

        # Get item
        item = models.ObjectClass.objects.get(name='pokemon')
        self.ra.register(item, models.STATES.standard, self.su)

        response = self.client.get(reverse('aristotle:search')+"?q=pokemon")
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.context['page'].object_list),1)


    def test_facet_search(self):
        self.logout()

        with reversion.create_revision():
            oc = models.ObjectClass.objects.create(
                name="Pokemon",
                definition="a Pocket monster"
            )
            dec = models.DataElementConcept.objects.create(
                name="Pokemon—Combat Power",
                definition="a Pokemons combat power",
                objectClass=oc
            )
            de = models.DataElement.objects.create(
                name="Pokemon—Combat Power, Go",
                definition="a Pokemons combat power as recorded in the Pokemon-Go scale",
                dataElementConcept=dec
            )

        self.login_superuser()

        response = self.client.get(reverse('aristotle:search')+"?q=pokemon")

        objs = response.context['page'].object_list
        self.assertEqual(len(objs),3)
        extra_facets = response.context['form'].extra_facet_fields

        self.assertTrue(len(extra_facets) == 2)
        self.assertTrue('data_element_concept' in [f[0] for f in extra_facets] )
        self.assertTrue('object_class' in [f[0] for f in extra_facets] )

        # Confirm spaces are included in the facet
        self.assertTrue(dec.name in [v[0] for v in dict(extra_facets)['data_element_concept']['values']])

        psqs = get_permission_sqs()
        psqs = psqs.auto_query('pokemon').apply_permission_checks(self.su)
        self.assertEqual(len(psqs),3)

        response = self.client.get(reverse('aristotle:search')+"?q=pokemon")
        objs = response.context['page'].object_list
        self.assertEqual(len(objs),3)

        response = self.client.get(reverse('aristotle:search')+"?q=pokemon&f=object_class::%s"%oc.name)

        objs = response.context['page'].object_list
        self.assertEqual(len(objs),2)
        self.assertTrue(de.pk in [o.object.pk for o in objs])
        self.assertTrue(dec.pk in [o.object.pk for o in objs])

        response = self.client.get(reverse('aristotle:search')+"?q=pokemon&f=data_element_concept::%s"%dec.name.replace(' ','+'))

        objs = response.context['page'].object_list
        self.assertEqual(len(objs),2)
        self.assertTrue(de.pk in [o.object.pk for o in objs])
        self.assertTrue(dec.pk in [o.object.pk for o in objs])

        response = self.client.get(reverse('aristotle:search')+"?q=pokemon&models=aristotle_mdr.dataelement&f=data_element_concept::%s"%dec.name.replace(' ','+'))

        objs = response.context['page'].object_list
        self.assertEqual(len(objs),1)
        self.assertTrue(de.pk in [o.object.pk for o in objs])
        self.assertTrue(dec.pk not in [o.object.pk for o in objs])

    def test_model_search(self):
        self.logout()

        with reversion.create_revision():
            dec = models.DataElementConcept.objects.create(
                name="Pokemon-CP",
                definition="a Pokemons combat power"
            )
            de = models.DataElement.objects.create(
                name="Pokemon-CP, Go",
                definition="a Pokemons combat power as recorded in the Pokemon-Go scale",
                dataElementConcept=dec
            )

        self.login_superuser()

        response = self.client.get(reverse('aristotle:search')+"?q=pokemon")

        objs = response.context['page'].object_list
        self.assertEqual(len(objs),2)

        response = self.client.get(reverse('aristotle:search')+"?q=pokemon&models=aristotle_mdr.dataelement")

        objs = response.context['page'].object_list
        self.assertEqual(len(objs),1)
        self.assertEqual(objs[0].object.pk,de.pk)

    def test_values_in_conceptual_domain_search(self):
        # For bug #676
        PSQS = get_permission_sqs()
        psqs = PSQS.auto_query('flight').apply_permission_checks(self.su)
        self.assertEqual(len(psqs),0)
        psqs = PSQS.auto_query('mutations').apply_permission_checks(self.su)
        self.assertEqual(len(psqs),0)

        cd = models.ConceptualDomain.objects.create(
                name="Mutation",
                definition="List of mutations",
            )
        for i, power in enumerate(['flight', 'healing', 'invisiblilty']):
            models.ValueMeaning.objects.create(
                name=power, definition=power, order=i,
                conceptual_domain=cd
            )

        psqs = PSQS.auto_query('mutations').apply_permission_checks(self.su)
        self.assertEqual(len(psqs),1)
        self.assertEqual(psqs[0].object.pk, cd.pk)

        psqs = PSQS.auto_query('flight').apply_permission_checks(self.su)
        self.assertEqual(len(psqs),1)
        self.assertEqual(psqs[0].object.pk, cd.pk)

    def test_values_in_value_domain_search(self):
        # For bug #676
        PSQS = get_permission_sqs()
        psqs = PSQS.auto_query('flight').apply_permission_checks(self.su)
        self.assertEqual(len(psqs),0)
        psqs = PSQS.auto_query('mutations').apply_permission_checks(self.su)
        self.assertEqual(len(psqs),0)
        psqs = PSQS.auto_query('FLT').apply_permission_checks(self.su)
        self.assertEqual(len(psqs),0)

        # with reversion.create_revision():
        vd = models.ValueDomain.objects.create(
                name="Mutation",
                definition="Coded list of mutations",
            )
        for i, data in enumerate([("FLT", 'flight'), ("HEAL", 'healing'), ("INVIS", 'invisiblilty')]):
            code, power = data
            models.PermissibleValue.objects.create(
                value=code, meaning=power, order=i,
                valueDomain=vd
            )

        psqs = PSQS.auto_query('mutations').apply_permission_checks(self.su)
        self.assertEqual(len(psqs), 1)
        self.assertEqual(psqs[0].object.pk, vd.pk)
        psqs = PSQS.auto_query('flight').apply_permission_checks(self.su)
        self.assertEqual(len(psqs), 1)
        self.assertEqual(psqs[0].object.pk, vd.pk)
        psqs = PSQS.auto_query('FLT').apply_permission_checks(self.su)
        self.assertEqual(len(psqs), 1)
        self.assertEqual(psqs[0].object.pk, vd.pk)

    def test_number_search_results(self):

        rpp_values = getattr(settings, 'RESULTS_PER_PAGE', [20])

        #add new test data
        letters = ""
        for i in range(100):
            letters += random.choice(string.ascii_letters)
            letters += ' '

        self.login_regular_user()

        random_wg = models.Workgroup.objects.create(name="random_wg", stewardship_organisation=self.steward_org)

        item_random = [
            models.ObjectClass.objects.create(name=t, definition='random', workgroup=random_wg)
            for t in letters.split()]

        for item in item_random:
            registered = self.ra.register(item,models.STATES.standard,self.su)
            self.assertTrue(item in registered['success'])

        #test default number of items
        response = self.client.get(reverse('aristotle:search')+"?q=random")
        self.assertEqual(response.context['page'].end_index(),rpp_values[0])

        for val in rpp_values:
            response = self.client.get(reverse('aristotle:search')+"?q=random&rpp=" + str(val))
            self.assertEqual(response.context['page'].end_index(),val)

        #test with invalid number (drops back to default)
        response = self.client.get(reverse('aristotle:search')+"?q=random&rpp=92")
        self.assertEqual(response.context['page'].end_index(),rpp_values[0])

        self.logout()

        #delete newly added data
        for item in item_random:
            item.delete()

        random_wg.delete()

    def test_filters_without_text(self):
        """Test filtering objects without any search text"""
        # Create data element concept test object
        dec = models.DataElementConcept.objects.create(
            name='Person―Speed',
            definition='A persons speed',
            workgroup=self.avengers_wg
        )
        registered = self.ra.register(dec, models.STATES.standard, self.su)

        url = reverse('aristotle:search') + '?category=metadata&q=&models=aristotle_mdr.dataelementconcept'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Make sure we recieve only the data element concept
        page = response.context['page']
        self.assertEqual(models.DataElementConcept.objects.count(), 1)
        self.assertEqual(len(page), 1)
        self.assertEqual(page[0].pk, dec.pk)



@tag('token_search')
class TestTokenSearch(TestCase):
    def tearDown(self):
        call_command('clear_index', interactive=False, verbosity=0)

    @reversion.create_revision()
    def setUp(self):
        call_command('clear_index', interactive=False, verbosity=0)
        # These are really terrible Object Classes, but I was bored and needed to spice things up.
        # Technically, the Object Class would be "Mutant"
        super().setUp()
        import haystack
        haystack.connections.reload('default')

        self.su = get_user_model().objects.create_superuser('super@example.com','user')
        self.steward_org = models.StewardOrganisation.objects.create(name="Test SO")
        self.ra = models.RegistrationAuthority.objects.create(name="Kelly Act", stewardship_organisation=self.steward_org)
        self.registrar = get_user_model().objects.create_user('william.styker@weaponx.mil','mutantsMustDie')
        self.ra.giveRoleToUser('registrar',self.registrar)
        xmen = "wolverine professorX cyclops iceman angel beast phoenix storm nightcrawler"
        self.xmen_wg = models.Workgroup.objects.create(name="X Men", stewardship_organisation=self.steward_org)
        self.xmen_wg.save()

        self.item_xmen = [
            models.ObjectClass.objects.create(
                name=t,
                version="0.%d.0"%(v+1),
                definition="known x-man",
                workgroup=self.xmen_wg
            )
            for v,t in enumerate(xmen.split())
        ]

        self.item_xmen.append(
            models.Property.objects.create(
                name="Power",
                definition="What power a mutant has?",
                workgroup=self.xmen_wg
            )
        )

        for item in self.item_xmen:
            self.ra.register(item,models.STATES.standard,self.su)

    def add_identifiers(self):
        namespace = ident_models.Namespace.objects.create(
            stewardship_organisation=self.steward_org,
            shorthand_prefix='pre'
        )
        alt_namespace = ident_models.Namespace.objects.create(
            stewardship_organisation=self.steward_org,
            shorthand_prefix='xmn'
        )
        self.custom_namespace = ident_models.Namespace.objects.create(
            stewardship_organisation=self.steward_org,
            shorthand_prefix='ctm'
        )

        for xman in self.item_xmen:
            ident_models.ScopedIdentifier.objects.create(
                namespace=namespace,
                identifier=xman.name[:3],
                version='1',
                concept=xman
            )
            ident_models.ScopedIdentifier.objects.create(
                namespace=alt_namespace,
                identifier=xman.name[:3],
                version='1',
                concept=xman
            )

    def add_new_identifier(self, obj, identifier, version='1'):
        ident_models.ScopedIdentifier.objects.create(
            namespace=self.custom_namespace,
            identifier=identifier,
            version=version,
            concept=obj
        )

    def query_search(self, searchtext):
        query_params = '?q=' + searchtext
        response = self.client.get(reverse('aristotle:search')+query_params)
        self.assertEqual(response.status_code,200)
        return response.context['page'].object_list

    def test_token_version_search(self):
        self.assertEqual(models.ObjectClass.objects.get(version='0.1.0').name,"wolverine")

        response = self.client.get(reverse('aristotle:search')+"?q=version:0.1.0")
        self.assertEqual(response.status_code,200)
        objs = response.context['page'].object_list
        self.assertEqual(len(objs),1)
        self.assertEqual(objs[0].object.name,"wolverine")

    def test_token_type_search(self):
        response = self.client.get(reverse('aristotle:search')+"?q=type:property")
        self.assertEqual(response.status_code,200)
        objs = response.context['page'].object_list
        self.assertEqual(len(objs),1)
        self.assertEqual(objs[0].object.name,"Power")

        response = self.client.get(reverse('aristotle:search')+"?q=type:p")
        self.assertEqual(response.status_code,200)
        objs = response.context['page'].object_list
        self.assertEqual(len(objs),1)
        self.assertEqual(objs[0].object.name,"Power")

    @tag('id_search')
    @unittest.skipIf('WhooshEngine' in settings.HAYSTACK_CONNECTIONS['default']['ENGINE'],
                     'Searching within a multivalue string is not supported in whoosh')
    def test_token_id_search_specific_ns(self):
        # Tests that only the identifier with the correct
        # namespace is returned when one is specified
        self.add_identifiers()
        objs = self.query_search('id:pre/ice')
        self.assertEqual(len(objs),1)
        self.assertEqual(objs[0].object.name,"iceman")

    @tag('id_search')
    @unittest.skipIf('WhooshEngine' in settings.HAYSTACK_CONNECTIONS['default']['ENGINE'],
                     'Searching within a multivalue string is not supported in whoosh')
    def test_token_id_search_general(self):
        # Tests that if only an identifier is used, all namespaces are returned
        self.add_identifiers()
        self.add_new_identifier(self.item_xmen[0], 'ice')
        objs = self.query_search('id:ice')
        self.assertEqual(len(objs),2)

    @tag('id_search')
    def test_token_namespace_search(self):
        # Tests namespace search returns all in that namespace
        self.add_identifiers()
        objs = self.query_search('ns:pre')
        self.assertEqual(len(objs),10)

    @tag('id_search')
    def test_token_id_version_search(self):
        # Tests that only correct version is returned when a version is given
        self.add_identifiers()
        self.add_new_identifier(self.item_xmen[0], 'test', '1')
        self.add_new_identifier(self.item_xmen[1], 'test', '2')
        objs = self.query_search('id:ctm/test/1')
        self.assertEqual(len(objs),1)
        self.assertEqual(objs[0].object.name,"wolverine")

    @tag('token_search')
    def test_token_statuses_search(self):
        # Tests that only the identifier with the correct
        # namespace is returned when one is specified
        objs = self.query_search('wolverine hs:standard')
        self.assertEqual(len(objs),1)
        self.assertEqual(objs[0].object.name,"wolverine")

        objs = self.query_search('wolverine statuses:standard')
        self.assertEqual(len(objs),1)
        self.assertEqual(objs[0].object.name,"wolverine")

        animal = models.ObjectClass.objects.create(
            name="Wolverine (animal)",version="0.0.1",
            definition="An regular animal found on Earth-1218 - not a mutant from a comic book."
        )
        self.ra.register(animal,models.STATES.recorded,self.su)

        objs = self.query_search('wolverine statuses:standard,recorded')
        self.assertEqual(len(objs),2)
        objs = sorted(objs, key=lambda obj: len(obj.name))
        self.assertEqual(objs[0].object.name,"wolverine")
        self.assertEqual(objs[1].object.name,"Wolverine (animal)")

    def test_uuid_search(self):
        item = self.item_xmen[0]
        objs = self.query_search('uuid:{}'.format(item.uuid))
        self.assertEqual(len(objs), 1)
        self.assertEqual(objs[0].object, item)

    @unittest.skip("TODO: Fix this")
    def test_title_prioritisation(self):
        self.client.login(email='super@example.com', password='user')
        # Item with pokemon as name
        in_title_item = models.ObjectClass.objects.create(
            name='Pokemon',
            definition='Pocket monsters',
        )
        # Item with pokemon in definition multiple times
        in_definition_item = models.ObjectClass.objects.create(
            name='Pocket monsters',
            definition='Pokemon are so good. Pokemon. Pokemon',
        )
        objs = self.query_search('pokemon')
        self.assertEqual(len(objs), 2)
        self.assertEqual(objs[0].object, in_title_item)


class TestSearchDescriptions(TestCase):
    """
    Test the 'form to plain text' description generator
    """
    def setUp(self):
        self.steward_org = models.StewardOrganisation.objects.create(name="Test SO")

    def test_descriptions(self):
        from aristotle_mdr.forms.search import PermissionSearchForm as PSF
        from aristotle_mdr.templatetags.aristotle_search_tags import \
            search_describe_filters as gen

        ra = models.RegistrationAuthority.objects.create(name='Filter RA', stewardship_organisation=self.steward_org)

        filters = {'models':['aristotle_mdr.objectclass']}
        form = PSF(filters)

        if not form.is_valid(): # pragma: no cover
            # If this branch happens, we messed up the test bad.
            print(form.errors)
            self.assertTrue('programmer' is 'good')

        description = gen(form)
        self.assertTrue('Item type is Object Classes' == description)
        self.assertTrue('and' not in description)

        filters = {'models':[
            'aristotle_mdr.objectclass',
            'aristotle_mdr.property',
            'aristotle_mdr.dataelement',
        ]}
        form = PSF(filters)
        if not form.is_valid(): # pragma: no cover
            print(form.errors)
            self.assertTrue('programmer' is 'good')

        description = gen(form)

        self.assertTrue(
            'item type is object classes, properties or data elements' == description.lower()
        )
        self.assertTrue('and' not in description)

        filters = {'models':['aristotle_mdr.objectclass'],'ra':[str(ra.pk)]}
        form = PSF(filters)
        if not form.is_valid(): # pragma: no cover
            print(form.errors)
            self.assertTrue('programmer' is 'good')

        description = gen(form)

        self.assertTrue('Item type is Object Classes' in gen(form))
        self.assertTrue('registration authority is %s'%ra.name.lower() in gen(form).lower())
        self.assertTrue('and' in description)

        filters = {
            'models':['aristotle_mdr.objectclass'],
            'res':0
        }
        form = PSF(filters)

        if not form.is_valid(): # pragma: no cover
            # If this branch happens, we messed up the test bad.
            print(form.errors)
            self.assertTrue('programmer' is 'good')

        description = gen(form)
        self.assertTrue('Item type is Object Classes' in description)
        self.assertTrue('and' in description)
        self.assertTrue('Item visibility state is Public' in description)

