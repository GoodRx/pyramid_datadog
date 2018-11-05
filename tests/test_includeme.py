import mock
from mock import patch
from pyramid_datadog import (
    includeme,
    configure_metrics,
    on_app_created,
    on_new_request,
    on_before_traversal,
    on_context_found,
    on_before_render,
    on_new_response,
    time_ms,
)


def test_includeme():
    from pyramid.events import (
        ApplicationCreated,
        NewResponse,
        NewRequest,
        ContextFound,
        BeforeTraversal,
        BeforeRender)

    config = mock.Mock()

    includeme(config)
    config.add_directive.assert_called_once_with('configure_metrics', configure_metrics)
    config.add_subscriber.assert_has_calls([
        mock.call(on_app_created, ApplicationCreated),
        mock.call(on_new_request, NewRequest),
        mock.call(on_before_traversal, BeforeTraversal),
        mock.call(on_context_found, ContextFound),
        mock.call(on_before_render, BeforeRender),
        mock.call(on_new_response, NewResponse),
    ])


def test_configure_metrics():
    config = mock.Mock()
    datadog_metrics = mock.Mock()
    configure_metrics(config, datadog_metrics)

    config.registry.datadog == datadog_metrics


def test_on_app_created():
    app_created_event = mock.Mock()
    app_created_event.app.registry.datadog = mock.Mock()
    on_app_created(app_created_event)

    app_created_event.app.registry.datadog.event.assert_called_once_with(
        'Pyramid application started',
        'Pyramid application started',
    )


@patch('pyramid_datadog.time_ms')
def test_on_new_request(time_ms_mock):
    new_request_event = mock.Mock()
    time_ms_mock.return_value = 1

    on_new_request(new_request_event)

    assert new_request_event.request.timings['new_request_start'] == 1


@patch('pyramid_datadog.time_ms')
def test_on_before_traversal(time_ms_mock):
    before_traversal_event = mock.Mock()
    before_traversal_event.request.timings = {}
    before_traversal_event.request.timings['new_request_start'] = 1
    time_ms_mock.return_value = 2

    on_before_traversal(before_traversal_event)

    (metric, value), kwargs = before_traversal_event.request.registry.datadog.timing.call_args
    assert value == 1


@patch('pyramid_datadog.time_ms')
def test_on_context_found(time_ms_mock):
    context_found_event = mock.Mock()
    context_found_event.request.timings = {}
    context_found_event.request.timings['new_request_start'] = 1
    time_ms_mock.return_value = 3

    on_context_found(context_found_event)

    assert context_found_event.request.timings['view_code_start'] == 3
    (metric, value), kwargs = context_found_event.request.registry.datadog.timing.call_args
    assert value == 2


@patch('pyramid_datadog.time_ms')
def test_on_before_render(time_ms_mock):
    before_render_event = mock.Mock()
    before_render_event = {'request': mock.Mock()}
    timings = before_render_event['request'].timings = {}
    before_render_event['request'].matched_route.name = 'route_name'
    timings['view_code_start'] = 3
    time_ms_mock.return_value = 4

    on_before_render(before_render_event)

    assert timings['view_duration'] == 1
    assert timings['before_render_start'] == 4

    (metric, value), kwargs = before_render_event['request'].registry.datadog.timing.call_args
    assert value == 1


def test_on_before_render_no_timings():
    """
    If ``request.timings`` doesn't exist, don't add timings when handling
    ``BeforeRender``.
    """
    from pyramid.testing import DummyRequest

    request = DummyRequest()
    before_render_event = mock.Mock()
    before_render_event = {'request': request}
    request.registry.datadog = mock.Mock()

    on_before_render(before_render_event)

    before_render_event['request'].registry.datadog.timing.assert_not_called()


@patch('pyramid_datadog.time_ms')
def test_on_before_render_no_view_code_start(time_ms_mock):
    before_render_event = mock.Mock()
    before_render_event = {'request': mock.Mock()}
    timings = before_render_event['request'].timings = {}
    before_render_event['request'].matched_route.name = 'route_name'
    time_ms_mock.return_value = 4

    on_before_render(before_render_event)

    assert timings == {'before_render_start': 4}

    before_render_event['request'].registry.datadog.timing.assert_not_called()


@patch('pyramid_datadog.time_ms')
def test_on_before_render_no_matched_route(time_ms_mock):
    before_render_event = mock.Mock()
    before_render_event = {'request': mock.Mock()}

    before_render_event['request'].matched_route = None

    timings = before_render_event['request'].timings = {}
    timings['view_code_start'] = 3
    time_ms_mock.return_value = 4

    on_before_render(before_render_event)

    assert timings['view_duration'] == 1
    assert timings['before_render_start'] == 4

    (metric, value), kwargs = before_render_event['request'].registry.datadog.timing.call_args
    assert value == 1


@patch('pyramid_datadog.time_ms')
def test_on_new_response(time_ms_mock):
    new_response_event = mock.Mock()
    time_ms_mock.return_value = 5
    timings = new_response_event.request.timings = {}
    timings['new_request_start'] = 1
    timings['before_render_start'] = 4

    on_new_response(new_response_event)

    assert timings['request_duration'] == 4
    assert timings['template_render_duration'] == 1
    new_response_event.request.registry.datadog.timing.assert_has_calls([
        mock.call(mock.ANY, 1, tags=mock.ANY),
        mock.call(mock.ANY, 4, tags=mock.ANY),
    ])


def test_on_new_response_no_timings():
    """
    If ``request.timings`` doesn't exist, don't add timings when handling
    ``NewResponse``.
    """
    from pyramid.testing import DummyRequest

    new_response_event = mock.Mock()
    new_response_event.request = DummyRequest()
    new_response_event.request.registry.datadog = mock.Mock()

    on_new_response(new_response_event)

    new_response_event.request.registry.datadog.timing.assert_not_called()


@patch('time.time')
def test_time_ms(mock_time):
    mock_time.return_value = 1
    return_value = time_ms()
    assert return_value == 1000


def test_500():
    from pyramid.config import Configurator
    from webtest import TestApp

    mock_metric = mock.Mock()

    def main(global_config, **settings):
        config = Configurator(settings=settings)
        config.include('pyramid_datadog')

        config.configure_metrics(mock_metric)

        def test_view(request):
            from pyramid.httpexceptions import HTTPInternalServerError
            return HTTPInternalServerError()

        config.add_route('home', '/')
        config.add_view(test_view, route_name='home', renderer='json')

        return config.make_wsgi_app()

    app = main({})
    app = TestApp(app)
    app.get('/', status=500)

    mock_metric.timing.assert_has_calls([
        mock.call('pyramid.request.duration.route_match', mock.ANY),
        mock.call('pyramid.request.duration.traversal', mock.ANY),
        mock.call('pyramid.request.duration.total', mock.ANY, tags=['route:home', 'status_code:500', 'status_type:5xx'])
    ])


def test_404():
    from pyramid.config import Configurator
    from webtest import TestApp

    mock_metric = mock.Mock()

    def main(global_config, **settings):
        config = Configurator(settings=settings)
        config.include('pyramid_datadog')

        config.configure_metrics(mock_metric)

        config.add_route('home', '/')

        return config.make_wsgi_app()

    app = main({})
    app = TestApp(app)
    app.get('/foo', status=404)
    mock_metric.timing.assert_has_calls([
        mock.call('pyramid.request.duration.route_match', mock.ANY),
        mock.call('pyramid.request.duration.traversal', mock.ANY),
        mock.call('pyramid.request.duration.total', mock.ANY, tags=['status_code:404', 'status_type:4xx'])
    ])


def test_200():
    from pyramid.config import Configurator
    from webtest import TestApp

    mock_metric = mock.Mock()

    def main(global_config, **settings):
        config = Configurator(settings=settings)
        config.include('pyramid_datadog')

        config.configure_metrics(mock_metric)

        def test_view(request):
            return {}

        config.add_route('home', '/')
        config.add_view(test_view, route_name='home', renderer='json')

        return config.make_wsgi_app()

    app = main({})
    app = TestApp(app)
    app.get('/')
    mock_metric.timing.assert_has_calls([
        mock.call('pyramid.request.duration.route_match', mock.ANY),
        mock.call('pyramid.request.duration.traversal', mock.ANY),
        mock.call('pyramid.request.duration.view', mock.ANY, tags=['route:home']),
        mock.call('pyramid.request.duration.template_render', mock.ANY, tags=['route:home']),
        mock.call('pyramid.request.duration.total', mock.ANY, tags=['route:home', 'status_code:200', 'status_type:2xx'])
    ])
