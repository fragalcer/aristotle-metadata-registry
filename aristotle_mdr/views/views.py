from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.core.exceptions import PermissionDenied, ImproperlyConfigured
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.urlresolvers import reverse
from django.db import transaction
from django.forms.models import modelformset_factory
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.template.defaultfilters import slugify
from django.template.loader import select_template
from django.utils.translation import ugettext_lazy as _
from django.views.generic import TemplateView
from django.utils import timezone
import datetime

import reversion
from reversion import revisions
from reversion import models as MMMM
from reversion.revisions import default_revision_manager

from aristotle_mdr.perms import user_can_view, user_can_edit, user_can_change_status
from aristotle_mdr import perms
from aristotle_mdr.utils import cache_per_item_user, concept_to_dict, construct_change_message, url_slugify_concept
from aristotle_mdr import forms as MDRForms
from aristotle_mdr import models as MDR
from aristotle_mdr.utils import concept_to_clone_dict

from haystack.views import SearchView

PAGES_PER_RELATED_ITEM = 15


class DynamicTemplateView(TemplateView):
    def get_template_names(self):
        return ['aristotle_mdr/static/%s.html' % self.kwargs['template']]

class HelpTemplateView(TemplateView):
    def get_template_names(self):
        return ['aristotle_mdr/static/help/%s.html' % self.kwargs['template']]

def get_if_user_can_view(objtype,user,iid):
    item = get_object_or_404(objtype,pk=iid)
    if user_can_view(user,item):
        return item
    else:
        return False

def render_if_user_can_view(item_type, request, *args, **kwargs):
    #request = kwargs.pop('request')
    return render_if_condition_met(request, user_can_view, item_type, *args,**kwargs)

@login_required
def render_if_user_can_edit(item_type, request, *args, **kwargs):
    request = kwargs.pop('request')
    return render_if_condition_met(request, user_can_edit, item_type, *args,**kwargs)

def download(request,downloadType,iid=None):
    """
    By default, ``aristotle_mdr.views.download`` is called whenever a URL matches
    the pattern defined in ``aristotle_mdr.urls_aristotle``::

        download/(?P<downloadType>[a-zA-Z0-9\-\.]+)/(?P<iid>\d+)/?

    This is passed into ``download`` which resolves the item id (``iid``), and
    determins if a user has permission to view the request item with that id. If
    a user is allowed to download this file, ``download`` iterates through each
    download type defined in ``ARISTOTLE_DOWNLOADS``.

    A download option tuple takes the following form form::

        ('file_type','display_name','font_awesome_icon_name','module_name'),

    With ``file_type`` allowing only ASCII alphanumeric and underscores,
    ``display_name`` can be any valid python string,
    ``font_awesome_icon_name`` can be any Font Awesome icon and
    ``module_name`` is the name of the python module that provides a downloader
    for this file type.

    For example, included with Aristotle-MDR is a PDF downloader which has the
    download definition tuple::

            ('pdf','PDF','fa-file-pdf-o','aristotle_mdr'),

    Where a ``file_type`` multiple is defined multiple times, **the last matching
    instance in the tuple is used**.

    Next, the module that is defined for a ``file_type`` is dynamically imported using
    ``exec``, and is wrapped in a ``try: except`` block to catch any exceptions. If
    the ``module_name`` does not match the regex ``^[a-zA-Z0-9\_]+$`` ``download``
    raises an exception.

    If the module is able to be imported, ``downloader.py`` from the given module
    is imported, this file **MUST** have a ``download`` function defined which returns
    a Django ``HttpResponse`` object of some form.
    """
    item = MDR._concept.objects.get_subclass(pk=iid)
    item = get_if_user_can_view(item.__class__,request.user, iid)
    if not item:
        if request.user.is_anonymous():
            return redirect(reverse('friendly_login')+'?next=%s' % request.path)
        else:
            raise PermissionDenied

    downloadOpts = getattr(settings, 'ARISTOTLE_DOWNLOADS', "")
    module_name = ""
    for d in downloadOpts:
        dt = d[0]
        if dt == downloadType:
            module_name = d[3]
    if module_name:
        import re
        if not re.search('^[a-zA-Z0-9\-\.]+$',downloadType): # pragma: no cover
            # Invalid downloadType
            raise ImproperlyConfigured
        elif not re.search('^[a-zA-Z0-9\_]+$',module_name): # pragma: no cover
            # bad module_name
            raise ImproperlyConfigured
        try:
            downloader = None
            # dangerous - we are really trusting the settings creators here.
            exec("import %s.downloader as downloader"%module_name)
            return downloader.download(request,downloadType,item)
        except TemplateDoesNotExist:
            # If the template doesn't exist lets tell the user not to try again
            raise Http404

    raise Http404

def concept(*args,**kwargs):
    return render_if_user_can_view(MDR._concept,*args,**kwargs)

def measure(request,iid,model_slug,name_slug):
    item = get_object_or_404(MDR.Measure,pk=iid).item
    template = select_template([item.template])
    context = RequestContext(request,
        {'item':item,
         #'view':request.GET.get('view','').lower(),
         #'last_edit': last_edit
            }
        )

    return HttpResponse(template.render(context))

    #return render_if_user_can_view(MDR.Measure,*args,**kwargs)

@cache_per_item_user(ttl=300, cache_post=False)
def render_if_condition_met(request,condition,objtype,iid,model_slug=None,name_slug=None,subpage=None):
    item = get_object_or_404(objtype,pk=iid).item
    if item._meta.model_name != model_slug or not slugify(item.name).startswith(str(name_slug)):
        return redirect(url_slugify_concept(item))
    if not condition(request.user, item):
        if request.user.is_anonymous():
            return redirect(reverse('friendly_login')+'?next=%s' % request.path)
        else:
            raise PermissionDenied

    # We add a user_can_edit flag in addition to others as we have odd rules around who can edit objects.
    isFavourite = request.user.is_authenticated () and request.user.profile.is_favourite(item)

    last_edit = default_revision_manager.get_for_object_reference(
            item.__class__,
            item.pk,
        ).first()

    default_template = "%s/concepts/%s.html"%(item.__class__._meta.app_label,item.__class__._meta.model_name)
    template = select_template([default_template,item.template])
    context = RequestContext(request,
        {'item':item,
         #'view':request.GET.get('view','').lower(),
         'isFavourite': isFavourite,
         'last_edit': last_edit
            }
        )

    return HttpResponse(template.render(context))

def item_history(request,iid):
    item = get_if_user_can_view(MDR._concept,request.user,iid)
    if not item:
        if request.user.is_anonymous():
            return redirect(reverse('friendly_login')+'?next=%s' % request.path)
        else:
            raise PermissionDenied
    item = item.item
    versions = default_revision_manager.get_for_object(item)
    from django.contrib.contenttypes.models import ContentType
    ct = ContentType.objects.get_for_model(item)
    versions = reversion.models.Version.objects.filter(content_type=ct,object_id=item.pk).order_by('-revision__date_created')

    page = render(request,"aristotle_mdr/actions/concept_history.html",{"item":item,'versions':versions})
    return page


def registrationHistory(request, iid):
    item = get_if_user_can_view(MDR._concept,request.user,iid)
    if not item:
        if request.user.is_anonymous():
            return redirect(reverse('friendly_login')+'?next=%s' % request.path)
        else:
            raise PermissionDenied

    history = item.statuses.order_by("registrationAuthority","-registrationDate")
    out = {}
    for status in history:
        if status.registrationAuthority in out.keys():
            out[status.registrationAuthority].append(status)
        else:
            out[status.registrationAuthority] = [status]

    return render(request,"aristotle_mdr/registrationHistory.html",
            {'item':item,
             'history': out
                }
            )

def edit_item(request,iid,*args,**kwargs):
    item = get_object_or_404(MDR._concept,pk=iid).item
    if not user_can_edit(request.user, item):
        if request.user.is_anonymous():
            return redirect(reverse('friendly_login')+'?next=%s' % request.path)
        else:
            raise PermissionDenied

    base_form = MDRForms.wizards.subclassed_edit_modelform(item.__class__)
    if request.method == 'POST': # If the form has been submitted...
        form = base_form(request.POST,instance=item,user=request.user)
        new_wg = request.POST.get('workgroup',None)
        workgroup_changed = not(str(item.workgroup.pk) == (new_wg))

        if form.is_valid():
            workgroup_changed = item.workgroup.pk != form.cleaned_data['workgroup'].pk

            with transaction.atomic(), revisions.create_revision():
                change_comments = form.data.get('change_comments',None)
                item = form.save()
                reversion.revisions.set_user(request.user)
                if not change_comments:
                    change_comments = construct_change_message(request,form,None)
                reversion.revisions.set_comment(change_comments)
                return HttpResponseRedirect(url_slugify_concept(item))
    else:
        form = base_form(instance=item,user=request.user)
    return render(request,"aristotle_mdr/actions/advanced_editor.html",
            {"item":item,
             "form":form,
                }
            )

def clone_item(request,iid,*args,**kwargs):
    item_to_clone = get_object_or_404(MDR._concept,pk=iid).item
    if not user_can_edit(request.user, item_to_clone):
        if request.user.is_anonymous():
            return redirect(reverse('friendly_login')+'?next=%s' % request.path)
        else:
            raise PermissionDenied
    base_form = MDRForms.wizards.subclassed_modelform(item_to_clone.__class__)
    if request.method == 'POST': # If the form has been submitted...
        form = base_form(request.POST,user=request.user)

        if form.is_valid():
            with transaction.atomic(), revisions.create_revision():
                new_clone = form.save()
                reversion.revisions.set_user(request.user)
                reversion.revisions.set_comment("Cloned from %s (id: %s)"%(item_to_clone.name,str(item_to_clone.pk)))
                return HttpResponseRedirect(url_slugify_concept(new_clone))
    else:
        form = base_form(initial=concept_to_clone_dict(item_to_clone),user=request.user)
    return render(request,"aristotle_mdr/create/clone_item.html",
            {"item":item_to_clone,
             "form":form,
                }
            )

def unauthorised(request, path=''):
    if request.user.is_anonymous():
        return render(request,"401.html",{"path":path,"anon":True,},status=401)
    else:
        return render(request,"403.html",{"path":path,"anon":True,},status=403)



def create_list(request):
    if request.user.is_anonymous():
        return redirect(reverse('friendly_login')+'?next=%s' % request.path)
    if not perms.user_is_editor(request.user):
        raise PermissionDenied

    aristotle_apps = getattr(settings, 'ARISTOTLE_SETTINGS', {}).get('CONTENT_EXTENSIONS',[])
    aristotle_apps += ["aristotle_mdr"]

    from django.contrib.contenttypes.models import ContentType
    models = ContentType.objects.filter(app_label__in=aristotle_apps).all()
    out = {}

    for m in models:
        if issubclass(m.model_class(),MDR._concept) and not m.model.startswith("_"):
            # Only output subclasses of 11179 concept
            app_models = out.get(m.app_label,{'app':None,'models':[]})
            if app_models['app'] is None:
                try:
                    app_models['app'] = getattr(apps.get_app_config(m.app_label),'verbose_name')
                except:
                    app_models['app'] = "No name" # Where no name is configured in the app_config, set a dummy so we don't keep trying
            app_models['models'].append((m,m.model_class()))
            out[m.app_label] = app_models

    return render(request,"aristotle_mdr/create/create_list.html",
        {'models':out,}
        )


@login_required
def toggleFavourite(request, iid):
    item = get_object_or_404(MDR._concept,pk=iid).item
    if not user_can_view(request.user, item):
        if request.user.is_anonymous():
            return redirect(reverse('friendly_login')+'?next=%s' % request.path)
        else:
            raise PermissionDenied
    request.user.profile.toggleFavourite(item)
    if request.GET.get('next',None):
        return redirect(request.GET.get('next'))
    return redirect(url_slugify_concept(item))

def registrationauthority(request,iid,*args,**kwargs):
    objtype = MDR.RegistrationAuthority
    if iid is None:
        app_name = objtype._meta.app_label
        return redirect(reverse("%s:about"%app_name,args=["".join(objtype._meta.verbose_name.lower().split())]))
    item = get_object_or_404(objtype,pk=iid).item

    return render(request,item.template,
        {'item':item.item,}
        )

def allRegistrationAuthorities(request):
    ras = MDR.RegistrationAuthority.objects.order_by('name')
    return render(request,"aristotle_mdr/allRegistrationAuthorities.html",
        {'registrationAuthorities':ras}
        )

def about_all_items(request):

    aristotle_apps = getattr(settings, 'ARISTOTLE_SETTINGS', {}).get('CONTENT_EXTENSIONS',[])
    aristotle_apps += ["aristotle_mdr"]
    out = {}
    from django.contrib.contenttypes.models import ContentType
    if aristotle_apps:
        for app_label in aristotle_apps:
            app=apps.get_app_config(app_label)
            try:
                app.about_url = reverse('%s:about'%app_label)
            except:
                pass # if there is no about URL, thats ok.
            app.mymodels = ContentType.objects.filter(app_label=app_label).all()

            out[app_label]=app

    #models = ContentType.objects.filter(app_label__in=aristotle_apps).all()
    #out = {}
    #for m in models:
    #    if not m.model.startswith("_"):
    #        app_models = out.get(m.app_label,[])
    #        app_models.append(m.model_class())
    #        out[m.app_label] = app_models

    return render(request,"aristotle_mdr/static/all_items.html",{'models':out,})

# Actions

def mark_ready_to_review(request,iid):
    item = get_object_or_404(MDR._concept,pk=iid).item
    if not (item and user_can_edit(request.user,item)):
        if request.user.is_anonymous():
            return redirect(reverse('friendly_login')+'?next=%s' % request.path)
        else:
            raise PermissionDenied

    if request.method == 'POST': # If the form has been submitted...
        if item.is_registered:
            raise PermissionDenied
        else:
            item.readyToReview = not item.readyToReview
            item.save()
        return HttpResponseRedirect(url_slugify_concept(item))
    else:
        return render(request,"aristotle_mdr/actions/mark_ready_to_review.html",
            {"item":item,}
            )

def changeStatus(request, iid):
    item = get_object_or_404(MDR._concept,pk=iid).item
    if not (item and user_can_change_status(request.user,item)):
        if request.user.is_anonymous():
            return redirect(reverse('friendly_login')+'?next=%s' % request.path)
        else:
            raise PermissionDenied
    # There would be an else here, but both branches above return,
    # so we've chopped it out to prevent an arrow anti-pattern.
    if request.method == 'POST': # If the form has been submitted...
        form = MDRForms.ChangeStatusForm(request.POST,user=request.user) # A form bound to the POST data
        if form.is_valid():
            # process the data in form.cleaned_data as required
            ras = form.cleaned_data['registrationAuthorities']
            state = form.cleaned_data['state']
            regDate = form.cleaned_data['registrationDate']
            cascade = form.cleaned_data['cascadeRegistration']
            changeDetails = form.cleaned_data['changeDetails']
            for ra in ras:
                if cascade:
                    register_method = ra.cascaded_register
                else:
                    register_method = ra.register

                register_method(item,state,request.user,
                        changeDetails=changeDetails,
                        registrationDate=regDate,
                    )
                # TODO: notification and message on success/failure
            return HttpResponseRedirect(url_slugify_concept(item))
    else:
        form = MDRForms.ChangeStatusForm(user=request.user)
    return render(request,"aristotle_mdr/actions/changeStatus.html",
            {"item":item,
             "form":form,
                }
            )
from reversion_compare.mixins import CompareMixin, CompareMethodsMixin
class Comparator(CompareMixin):
    def __init__(self,item_a,item_b,obj):
        self.item_a=item_a
        self.item_b=item_b
        self.obj=obj

def compare_concepts(request,obj_type=None):
    qs = MDR._concept.objects.visible(request.user)
    form = MDRForms.CompareConceptsForm(request.GET,user=request.user,qs=qs) # A form bound to the POST data
    comparison = {}
    item_a = request.GET.get('item_a',None)
    item_b = request.GET.get('item_b',None)

    context = {"item_a":item_a,
         "item_b":item_b,
            }

    if form.is_valid():
        item_a = get_object_or_404(MDR._concept,pk=item_a).item
        item_b = get_object_or_404(MDR._concept,pk=item_b).item

        from django.contrib.contenttypes.models import ContentType
        revs=[]
        for item in [item_a,item_a]:
            versions = default_revision_manager.get_for_object(item)
            ct = ContentType.objects.get_for_model(item)
            version = MMMM.Version.objects.filter(content_type=ct,object_id=item.pk).order_by('-revision__date_created').first()
            revs.append(version)
        if revs[0] is None:
            form.add_error('item_a','This field has no revisions. A comparison cannot be made')
        if revs[1] is None:
            form.add_error('item_b','This field has no revisions. A comparison cannot be made')
        if revs[0] is not None and revs[1] is not None:
            obj = item_a
            comparator = Comparator(*revs,obj=obj)
            version1 = revs[0]
            version2 = revs[1]
            version1 = MMMM.Version.objects.filter(content_type=ct,object_id=item_a.pk).order_by('-revision__date_created').first()
            version2 = MMMM.Version.objects.filter(content_type=ct,object_id=item_a.pk).order_by('-revision__date_created').last()

            compare_data_a, has_unfollowed_fields_a = comparator.compare(obj, version1, version2)
            compare_data_b, has_unfollowed_fields_b = comparator.compare(obj, version2, version1)
    
            has_unfollowed = has_unfollowed_fields_a or has_unfollowed_fields_b
            
            comparison = {}
            for field_diff_a in compare_data_a:
                name = field_diff_a['field'].name
                x = comparison.get(name,{})
                x['field'] = field_diff_a['field']
                x['a'] = field_diff_a['diff']
                comparison[name] = x
            for field_diff_b in compare_data_b:
                name = field_diff_b['field'].name
                comparison.get(name,{})['b'] = field_diff_b['diff']
    
            same = {}
            for f in item_a._meta.fields:
                if f.name not in comparison.keys():
                    same[f.name] = {'field':f,'value':getattr(item_a, f.name)}
                if f.name.startswith('_'):
                    #hidden field
                    comparison.pop(f.name,None)
                    same.pop(f.name,None)
    
            hidden_fields = ['readyToReview','workgroup','created','modified','id']
            for h in hidden_fields:
                comparison.pop(h,None)
                same.pop(h,None)

            only_a = {}
            for f in item_a._meta.fields:
                if f not in item_b._meta.fields and\
                    f not in comparison.keys() and\
                    f not in same.keys()\
                    and f.name not in hidden_fields:
                    only_a[f.name] = {'field':f,'value':getattr(item_a, f.name)}

            only_b = {}
            for f in item_b._meta.fields:
                if f not in item_a._meta.fields and\
                    f not in comparison.keys() and\
                    f not in same.keys()\
                    and f.name not in hidden_fields:
                    only_b[f.name] = {'field':f,'value':getattr(item_b, f.name)}
                    
            context.update({
                "comparison":comparison,
                "same":same,
                "only_a":only_a,
                "only_b":only_b,
            })
    context.update({"form":form,})
            #comparison = {'a':compare_data_a, 'b':compare_data_b}
    return render(request,"aristotle_mdr/actions/compare_items.html",context)

def supersede(request, iid):
    item = get_object_or_404(MDR._concept,pk=iid).item
    if not (item and user_can_edit(request.user,item)):
        if request.user.is_anonymous():
            return redirect(reverse('friendly_login')+'?next=%s' % request.path)
        else:
            raise PermissionDenied
    qs=item.__class__.objects.all()
    if request.method == 'POST': # If the form has been submitted...
        form = MDRForms.SupersedeForm(request.POST,user=request.user,item=item,qs=qs) # A form bound to the POST data
        if form.is_valid():
            item.superseded_by = form.cleaned_data['newerItem']
            item.save()
            return HttpResponseRedirect(url_slugify_concept(item))
    else:
        form = MDRForms.SupersedeForm(item=item,user=request.user,qs=qs)
    return render(request,"aristotle_mdr/actions/supersedeItem.html",
            {"item":item,
             "form":form,
                }
            )

def deprecate(request, iid):
    item = get_object_or_404(MDR._concept,pk=iid).item
    if not (item and user_can_edit(request.user,item)):
        if request.user.is_anonymous():
            return redirect(reverse('friendly_login')+'?next=%s' % request.path)
        else:
            raise PermissionDenied
    qs=item.__class__.objects.filter().editable(request.user)
    if request.method == 'POST': # If the form has been submitted...
        form = MDRForms.DeprecateForm(request.POST,user=request.user,item=item,qs=qs) # A form bound to the POST data
        if form.is_valid():
            # Check use the itemset as there are permissions issues and we want to remove some:
            #  Everything that was superseded, but isn't in the returned set
            #  Everything that was in the returned set, but isn't already superseded
            #  Everything left over can stay the same, as its already superseded
            #    or wasn't superseded and is staying that way.
            for i in item.supersedes.all():
                if i not in form.cleaned_data['olderItems'] and user_can_edit(request.user,i):
                    item.supersedes.remove(i)
            for i in form.cleaned_data['olderItems']:
                if user_can_edit(request.user,i): #Would check item.supersedes but its a set
                    item.supersedes.add(i)
            return HttpResponseRedirect(url_slugify_concept(item))
    else:
        form = MDRForms.DeprecateForm(user=request.user,item=item,qs=qs)
    return render(request,"aristotle_mdr/actions/deprecateItems.html",
            {"item":item,
             "form":form,
                }
            )

def valuedomain_value_edit(request,iid,value_type):
    item = get_object_or_404(MDR._concept,pk=iid).item
    if not user_can_edit(request.user,item):
        if request.user.is_anonymous():
            return redirect(reverse('friendly_login')+'?next=%s' % request.path)
        else:
            raise PermissionDenied
    value_model = { 'permissible'   : MDR.PermissibleValue,
                    'supplementary' : MDR.SupplementaryValue
                }.get(value_type, None)
    if not value_model:
        raise Http404

    num_values = value_model.objects.filter(valueDomain=item.id).count()
    if num_values > 0:
        extra = 0
    else:
        extra = 1
    ValuesFormSet = modelformset_factory(
        value_model,
        can_delete=True, # dont need can_order is we have an order field
        fields=('order','value','meaning'),
        extra=extra
        )
    if request.method == 'POST':
        formset = ValuesFormSet(request.POST, request.FILES)
        if formset.is_valid():
                with transaction.atomic(), reversion.create_revision():
                    item.save() # do this to ensure we are saving reversion records for the value domain, not just the values
                    formset.save(commit=False)
                    for form in formset.forms:
                        if form['value'].value() == '' and form['meaning'].value() == '':
                            continue # Skip over completely blank entries.
                        if form['id'].value() not in [deleted_record['id'].value() for deleted_record in formset.deleted_forms]:
                            value = form.save(commit=False) #Don't immediately save, we need to attach the value domain
                            value.valueDomain = item
                            value.save()
                    for obj in formset.deleted_objects:
                        obj.delete()
                    #formset.save(commit=True)
                    reversion.revisions.set_user(request.user)
                    reversion.revisions.set_comment(construct_change_message(request,None,[formset,]))

                return redirect(reverse("aristotle_mdr:item",args=[item.id]))
    else:
        formset = ValuesFormSet(
            queryset=value_model.objects.filter(valueDomain=item.id),
            initial=[{'order':num_values,'value':'','meaning':''}]
            )
    return render(request,"aristotle_mdr/actions/edit_value_domain_values.html",
            {'item':item,'formset': formset,'value_type':value_type,'value_model':value_model,}
        )

def extensions(request):
    content=[]
    aristotle_apps = getattr(settings, 'ARISTOTLE_SETTINGS', {}).get('CONTENT_EXTENSIONS',[])

    if aristotle_apps:
        for app_label in aristotle_apps:
            app=apps.get_app_config(app_label)
            try:
                app.about_url = reverse('%s:about'%app_label)
            except:
                pass # if there is no about URL, thats ok.
            content.append(app)

    content = list(set(content))
    aristotle_downloads = getattr(settings, 'ARISTOTLE_DOWNLOADS', [])
    downloads=dict()
    if aristotle_downloads:
        for download in aristotle_downloads:
            app_label = download[3]
            app_details = downloads.get(
                            app_label,
                            {'app':apps.get_app_config(app_label),'downloads':[]}
                        )
            try:
                app_details['about_url'] = reverse('%s:about'%app_label)
            except:
                pass # if there is no about URL, thats ok.
            app_details['downloads'].append(download)
            downloads[app_label]=app_details

    return render(request,"aristotle_mdr/static/extensions.html",
            {'content_extensions':content,'download_extensions':downloads,}
        )


def browse(request,oc_id=None,dec_id=None):
    if oc_id is None:
        items = MDR.ObjectClass.objects.order_by("name").public()
        return render(request,"aristotle_mdr/browse/objectClasses.html",
            {"items":items,
                }
            )
    elif oc_id is not None and dec_id is None:
        oc = get_object_or_404(MDR.ObjectClass,id=oc_id)
        items = MDR.DataElementConcept.objects.filter(objectClass=oc).order_by("name").public()
        return render(request,"aristotle_mdr/browse/dataElementConcepts.html",
            {"items":items,
             "objectClass":oc,
                }
            )
    elif oc_id is not None and dec_id is not None:
        # Yes, for now we ignore the Object Class. If the user is messing with IDs in the URL and things break thats their fault.
        dec = get_object_or_404(MDR.DataElementConcept,id=dec_id)
        items = MDR.DataElement.objects.filter(dataElementConcept=dec).order_by("name").public()
        return render(request,"aristotle_mdr/browse/dataElements.html",
            {"items":items,
             "dataElementConcept":dec,
                }
            )


#TODO: Check permissions for this
@login_required
def bulk_action(request):
    url = request.GET.get("next","/")
    message = ""
    if request.method == 'POST': # If the form has been submitted...
        actions = {
            "add_favourites":MDRForms.bulk_actions.AddFavouriteForm,
            "remove_favourites":MDRForms.bulk_actions.RemoveFavouriteForm,
            "change_state":MDRForms.bulk_actions.ChangeStateForm,
            }
        action = request.POST.get("bulkaction",None)
        if action is None:
            # no action, messed up, redirect
            return HttpResponseRedirect(url)
        if actions[action].confirm_page is None:
            # if there is no confirm page or extra details required, do the action and redirect
            form = actions[action](request.POST,user=request.user) # A form bound to the POST data
            if form.is_valid():
                message = form.make_changes()
                messages.add_message(request, messages.INFO, message)
            else:
                messages.add_message(request, messages.ERROR, form.errors)
            return HttpResponseRedirect(url)
        else:
            form = MDRForms.bulk_actions.BulkActionForm(request.POST,user=request.user)
            items = []
            if form.is_valid():
                items = form.cleaned_data['items']
            confirmed = request.POST.get("confirmed",None)

            if confirmed:
                # We've passed the confirmation page, try and save.
                form = actions[action](request.POST,user=request.user,items=items) # A form bound to the POST data
                # there was an error with the form redisplay
                if form.is_valid():
                    message = form.make_changes()
                    messages.add_message(request, messages.INFO, message)
                    return HttpResponseRedirect(url)
            else:
                # we need a confirmation, render the next form
                form = actions[action](request.POST,user=request.user,items=items)
            return render(request,actions[action].confirm_page,
                    {"items":items,
                     "form":form,
                     "next":url
                        }
                    )
    return HttpResponseRedirect(url)

# Search views

class PermissionSearchView(SearchView):
    def __call__(self, request):
        if 'addFavourites' in request.GET.keys():
            return bulkFavourite(request,url="aristotle:search")
        else:
            return super(PermissionSearchView, self).__call__(request)

    def build_form(self):
        form = super(self.__class__, self).build_form()
        form.request = self.request
        return form

