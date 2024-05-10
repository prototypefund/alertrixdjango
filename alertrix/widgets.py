from django.forms import Widget


class IntegerWithRecommendationsField(
    Widget,
):
    type = 'number'
    template_name = 'alertrix/widgets/integerwithrecommendationsfield.html'

    def __init__(self, options: list[dict]):
        self.options = options
        super().__init__()

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        list_id = context['widget']['name'] + '_options'
        context['widget']['type'] = self.type
        context['widget']['attrs']['list'] = list_id
        context['datalist'] = {
            'id': list_id,
            'options': self.options,
        }
        return context
