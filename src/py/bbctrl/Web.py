import os
import sys
import json
import tornado
import sockjs.tornado
import logging

import bbctrl


log = logging.getLogger('Web')



class LoadHandler(bbctrl.APIHandler):
    def get(self): self.write_json(self.ctrl.config.load())


class SaveHandler(bbctrl.APIHandler):
    def put_ok(self): self.ctrl.config.save(self.json)


class HomeHandler(bbctrl.APIHandler):
    def put_ok(self): self.ctrl.avr.home()


class StartHandler(bbctrl.APIHandler):
    def put_ok(self, path): self.ctrl.avr.start(path)


class StopHandler(bbctrl.APIHandler):
    def put_ok(self): self.ctrl.avr.stop()


class PauseHandler(bbctrl.APIHandler):
    def put_ok(self): self.ctrl.avr.pause(False)


class OptionalPauseHandler(bbctrl.APIHandler):
    def put_ok(self): self.ctrl.avr.pause(True)


class StepHandler(bbctrl.APIHandler):
    def put_ok(self): self.ctrl.avr.step()


class OverrideFeedHandler(bbctrl.APIHandler):
    def put_ok(self, value): self.ctrl.avr.override_feed(float(value))


class OverrideSpeedHandler(bbctrl.APIHandler):
    def put_ok(self, value): self.ctrl.avr.override_speed(float(value))


class Connection(sockjs.tornado.SockJSConnection):
    def heartbeat(self):
        self.timer = self.ctrl.ioloop.call_later(3, self.heartbeat)
        self.send_json({'heartbeat': self.count})
        self.count += 1


    def send_json(self, data):
        self.send(str.encode(json.dumps(data)))


    def on_open(self, info):
        self.ctrl = self.session.server.ctrl

        self.timer = self.ctrl.ioloop.call_later(3, self.heartbeat)
        self.count = 0;

        self.ctrl.clients.append(self)
        self.send_json(self.ctrl.state)


    def on_close(self):
        self.ctrl.ioloop.remove_timeout(self.timer)
        self.ctrl.clients.remove(self)


    def on_message(self, data):
        self.ctrl.input_queue.put(data + '\n')



class Web(tornado.web.Application):
    def __init__(self, ctrl):
        self.ctrl = ctrl

        handlers = [
            (r'/api/load', LoadHandler),
            (r'/api/save', SaveHandler),
            (r'/api/file(/.+)?', bbctrl.FileHandler),
            (r'/api/home', HomeHandler),
            (r'/api/start(/.+)', StartHandler),
            (r'/api/stop', StopHandler),
            (r'/api/pause', PauseHandler),
            (r'/api/pause/optional', OptionalPauseHandler),
            (r'/api/step', StepHandler),
            (r'/api/override/feed/([\d.]+)', OverrideFeedHandler),
            (r'/api/override/speed/([\d.]+)', OverrideSpeedHandler),
            (r'/(.*)', tornado.web.StaticFileHandler,
             {'path': bbctrl.get_resource('http/'),
              "default_filename": "index.html"}),
            ]

        router = sockjs.tornado.SockJSRouter(Connection, '/ws')
        router.ctrl = ctrl

        tornado.web.Application.__init__(self, router.urls + handlers)

        try:
            self.listen(ctrl.args.port, address = ctrl.args.addr)

        except Exception as e:
            log.error('Failed to bind %s:%d: %s', ctrl.args.addr,
                      ctrl.args.port, e)
            sys.exit(1)

        log.info('Listening on http://%s:%d/', ctrl.args.addr, ctrl.args.port)
