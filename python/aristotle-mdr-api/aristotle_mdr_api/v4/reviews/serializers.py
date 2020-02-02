from django.urls import reverse
from rest_framework import serializers

from aristotle_mdr.contrib.reviews.models import (
    ReviewRequest, ReviewComment, REVIEW_STATES,
    ReviewStatusChangeTimeline
)
from aristotle_mdr.perms import user_can_view

import logging

logger = logging.getLogger(__name__)
logger.debug("Logging started for " + __name__)


class StatusField(serializers.Field):
    choices = None

    def __init__(self, choices, **kwargs):
        self.choices = choices
        super().__init__(**kwargs)

    def validate(self, value):
        if value not in self.choices._identifier_map.keys():
            raise serializers.ValidationError(
                '"{}" is not a valid review state!'.format(value)
            )
        return value

    def to_internal_value(self, data):
        self.validate(data)
        return self.choices._identifier_map[data]

    def to_representation(self, data):
        return {y: x for x, y in self.choices._identifier_map.items()}[data]


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewRequest
        fields = ('message', 'status', 'requester', 'registration_authority')

    requester = serializers.HiddenField(
        default=serializers.CurrentUserDefault()
    )
    status = StatusField(
        choices=REVIEW_STATES,
        # style={'base_template': 'radio.html'}
    )

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['url'] = reverse('aristotle_reviews:review_details', args=[instance.id])
        return rep


class ReviewTimelineMixin:
    def validate_request(self, value):
        if not user_can_view(self.context['request'].user, value):
            raise serializers.ValidationError(
                'You don\'t have permission to comment on this review'
            )
        return value


class ReviewCommentSerializer(ReviewTimelineMixin, serializers.ModelSerializer):
    """ A comment """

    class Meta:
        model = ReviewComment
        fields = ('body', 'author', 'request', 'created')
        read_only_fields = ('created',)

    author = serializers.HiddenField(
        default=serializers.CurrentUserDefault()
    )


class ReviewStatusChangeSerializer(ReviewTimelineMixin, serializers.ModelSerializer):
    """ A comment """

    class Meta:
        model = ReviewStatusChangeTimeline
        fields = ('status', 'request', 'created', 'actor')
        read_only_fields = ('created',)

    actor = serializers.HiddenField(
        default=serializers.CurrentUserDefault()
    )


class ReviewUpdateAndCommentSerializer(ReviewSerializer):
    comment = ReviewCommentSerializer(required=False)
    status = StatusField(
        choices=REVIEW_STATES,
    )

    class Meta:
        model = ReviewRequest
        fields = ('status', 'comment',)

    def update(self, instance, validated_data):
        comment = validated_data.pop('comment', None)

        review = super().update(instance, validated_data)
        try:
            user = self.context.get("request", {}).user
        except:
            user = None
        update = ReviewStatusChangeTimeline.objects.create(
            request=review, status=review.status,
            actor=user
        )
        if comment:
            comment = ReviewComment.objects.create(request=review, author=user, **comment)
        else:
            comment = None
        return [review, comment]

    def to_representation(self, instance):
        data = {}
        for item in instance:
            if type(item) == ReviewRequest:
                data.update(super().to_representation(item))
            elif type(item) == ReviewComment:
                comment_serializer = ReviewCommentSerializer(item)
                data.update({'comment': comment_serializer.data})
        return data



