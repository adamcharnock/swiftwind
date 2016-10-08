from django.forms.models import (
    BaseInlineFormSet,
    inlineformset_factory,
    ModelForm,
    BaseModelFormSet,
    modelformset_factory)


def _all_errors(formset):
    errors = []
    for form in formset.forms:
        if hasattr(form, 'nested'):
            errors += _all_errors(form.nested)
        else:
            errors += form.non_field_errors() + \
                      [
                          '{}: {}: {}'.format(form.prefix, f, errors[0])
                          for f, errors
                          in form.errors.items()
                      ]
    return errors


class NestedMixin(object):

    def add_fields(self, form, index):

        # allow the super class to create the fields as usual
        super(NestedMixin, self).add_fields(form, index)

        form.nested = self.nested_formset_class(
            instance=form.instance,
            data=form.data if form.is_bound else None,
            files=form.files if form.is_bound else None,
            prefix='%s-%s' % (
                form.prefix,
                self.nested_formset_class.get_default_prefix(),
            ),
        )

    def is_valid(self):

        result = super(NestedMixin, self).is_valid()

        if self.is_bound:
            # look at any nested formsets, as well
            for form in self.forms:
                if not self._should_delete_form(form):
                    result = result and form.nested.is_valid()

        return result

    def save(self, commit=True):

        result = super(NestedMixin, self).save(commit=commit)

        for form in self.forms:
            if not self._should_delete_form(form):
                form.nested.save(commit=commit)

        return result

    def all_errors(self):
        """Get all errors present in this formset, recursing to any additional nested formsets."""
        return _all_errors(self)

    @property
    def media(self):
        return self.empty_form.media + self.empty_form.nested.media


class BaseNestedFormset(NestedMixin, BaseInlineFormSet):
    pass


class BaseNestedModelFormSet(NestedMixin, BaseModelFormSet):
    pass


class BaseNestedModelForm(ModelForm):

    def has_changed(self):

        return (
            super(BaseNestedModelForm, self).has_changed() or
            self.nested.has_changed()
        )


def nested_inline_formset_factory(parent_model, model, nested_formset,
                          form=BaseNestedModelForm,
                          formset=BaseNestedFormset, fk_name=None,
                          fields=None, exclude=None, extra=3,
                          can_order=False, can_delete=True,
                          max_num=None, formfield_callback=None,
                          widgets=None, validate_max=False,
                          localized_fields=None, labels=None,
                          help_texts=None, error_messages=None,
                          min_num=None, validate_min=None):
    kwargs = {
        'form': form,
        'formset': formset,
        'fk_name': fk_name,
        'fields': fields,
        'exclude': exclude,
        'extra': extra,
        'can_order': can_order,
        'can_delete': can_delete,
        'max_num': max_num,
        'formfield_callback': formfield_callback,
        'widgets': widgets,
        'validate_max': validate_max,
        'localized_fields': localized_fields,
        'labels': labels,
        'help_texts': help_texts,
        'error_messages': error_messages,
        'min_num': min_num,
        'validate_min': validate_min,
    }

    if kwargs['fields'] is None:
        kwargs['fields'] = [
            field.name
            for field in model._meta.local_fields
        ]

    NestedInlineFormSet = inlineformset_factory(
        parent_model,
        model,
        **kwargs
    )
    NestedInlineFormSet.nested_formset_class = nested_formset

    return NestedInlineFormSet


def nested_model_formset_factory(model, nested_formset,
                          form=BaseNestedModelForm,
                          formset=BaseNestedModelFormSet,
                          fields=None, exclude=None, extra=3,
                          can_order=False, can_delete=True,
                          max_num=None, formfield_callback=None,
                          widgets=None, validate_max=False,
                          localized_fields=None, labels=None,
                          help_texts=None, error_messages=None,
                          min_num=None, validate_min=None):
    kwargs = {
        'form': form,
        'formset': formset,
        'fields': fields,
        'exclude': exclude,
        'extra': extra,
        'can_order': can_order,
        'can_delete': can_delete,
        'max_num': max_num,
        'formfield_callback': formfield_callback,
        'widgets': widgets,
        'validate_max': validate_max,
        'localized_fields': localized_fields,
        'labels': labels,
        'help_texts': help_texts,
        'error_messages': error_messages,
        'min_num': min_num,
        'validate_min': validate_min,
    }

    # if kwargs['fields'] is None:
    #     kwargs['fields'] = [
    #         field.name
    #         for field in model._meta.local_fields
    #     ]

    NestedModelFormSet = modelformset_factory(
        model,
        **kwargs
    )
    NestedModelFormSet.nested_formset_class = nested_formset

    return NestedModelFormSet
