from ophyd import Device, Signal
from ophyd.status import Status


class DetectorA(Device):
    def __init__(self):
        self.name = "detector!"
        self.prefix = "prefix!"
        self._parent = None

    def stage(self):
        print("stage!")

    def trigger(self):
        print("trigger!")
        status = Status()
        status.set_finished()
        return status

    def describe(self):
        print("describe!")
        return {
            self.name: {
                "dtype": "number",
                "shape": [],
                "source": "where it came from (PV)"
            }
        }

    def read(self):
        print("read!")
        return {
            self.name: {"value": 1, "timestamp": 1.0}
        }

    def unstage(self):
        print("unstage!")


det1 = DetectorA()


class DetectorB(Device):
    def __init__(self, name, prefix):
        super().__init__(name=name, prefix=prefix)
        #self.name = "detector!"
        #self.prefix = "prefix!"
        #self._parent = None

    def stage(self):
        print("stage!")
        return [self]

    def trigger(self):
        print("trigger!")
        status = Status()
        status.set_finished()
        return status

    def describe(self):
        print("describe!")
        return {
            self.name: {
                "dtype": "number",
                "shape": [],
                "source": "where it came from (PV)"
            }
        }

    def read(self):
        print("read!")
        return {
            self.name: {"value": 1, "timestamp": 1.0}
        }

    def unstage(self):
        print("unstage!")
        return [self]


detb = DetectorB(name="name b", prefix="prefix-b")


class DetectorCSignal(Signal):
    def __init__(self, name, **kwargs):
        super().__init__(name=name, **kwargs)

    def describe(self):
        print("describe DetectorCSignal!")
        return {
            self.name: {
                "dtype": "number",
                "shape": [],
                "source": "where it came from (PV)"
            }
        }

    def stage(self):
        print("stage DetectorCSignal!")
        return [self]

    def read(self):
        print("read DetectorCSignal!")
        what_I_read = {
            self.name: {"value": self.get(), "timestamp": 1.0}
        }
        print(what_I_read)
        return what_I_read


from collections import deque
from pathlib import Path
from event_model import compose_resource
from ophyd import Component as Cpt, DeviceStatus, Staged


class ExternalFileReference(Signal):
    # the "value" of this Signal is not a real PV
    # but is intended to look like one

    def __init__(self, *args, shape, **kwargs):
        super().__init__(*args, **kwargs)
        self.shape = shape

    def describe(self):
        print("describe ExternalFileReferece!")
        res = super().describe()
        res[self.name].update(
            dict(
                external="FILESTORE:",
                dtype="array",
                shape=self.shape,
                dims=("x", "y"),
            )
        )
        return res

    def stage(self):
        print("stage ExternalFileRefernce!")
        return [self]


class DetectorC(Device):
    detector_c_signal = Cpt(DetectorCSignal, value=0)
    image_file = Cpt(ExternalFileReference, shape=(8, 8))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._staged = None
        self._resource = None
        self._datum_factory = None
        self._asset_docs_cache = deque()

        self._resource_root = Path(".").absolute()
        self._resource_path = Path("detector-data")
        self._resource_absolute_path = self._resource_root / self._resource_path

        self.image_file_path = None

    def stage(self):
        print("stage Detector C!")

        self._resource, self._datum_factory, _ = compose_resource(
            start={"uid": "this will not be used"},
            spec="ABC",
            root=str(self._resource_root),
            resource_path=str(self._resource_path),
            resource_kwargs={"image_shape": self.image_file.shape},
        )
        self._resource.pop("run_start")
        self._asset_docs_cache.append(("resource", self._resource))

        # stage the children
        self.detector_c_signal.stage()
        self.detector_c_signal.set(0)  # count trigger()s

        self.image_file.stage()
        self.image_file_path = self._resource_absolute_path / Path(f"detector-file.img")

        # create the external file
        self._resource_absolute_path.mkdir(exist_ok=True)
        with self.image_file_path.open("wt") as image_file:
            image_file.write(f"this is the header line\n")

        self._staged = Staged.yes
        return [self]

    def trigger(self):
        print("trigger Detector C!")
        if self._staged != Staged.yes:
            raise RuntimeError(
                "This device must be staged before being triggered"
            )

        trigger_count = self.detector_c_signal.get() + 1
        self.detector_c_signal.set(trigger_count)

        datum = self._datum_factory(datum_kwargs={"trigger_count": self.detector_c_signal.get()})
        print(f"datum: {datum}")

        # this is important
        self.image_file.put(datum["datum_id"])
        self._asset_docs_cache.append(("datum", datum))

        # "trigger" the detector
        with self.image_file_path.open("at") as image_file:
            image_file.write(f"this is line {trigger_count}\n")

        st = DeviceStatus(self)
        st.set_finished()

        return st

    def describe(self):
        print("describe DetectorC!")

        description = dict()
        description.update(self.detector_c_signal.describe())
        description.update(self.image_file.describe())
        print(description)

        return description

    def read(self):
        print("read DetectorC!")

        read_results = dict()
        read_results.update(self.detector_c_signal.read())

        # this is where datum_id goes
        read_results.update(self.image_file.read())

        print(read_results)
        return read_results

    def unstage(self):
        self._resource = self._datum_factory = None
        self._staged = Staged.no
        print("unstage Detector C!")
        return [self]

    def collect_asset_docs(self):
        print("collect asset docs from DetectorC!")
        items = list(self._asset_docs_cache)
        self._asset_docs_cache.clear()
        for item in items:
            yield item


detc = DetectorC(name="detectorc")

# unstage Detector C!
# Run aborted
# Traceback (most recent call last):
#   File "/home/jlynch/local/qas_pe_count/venv/lib/python3.6/site-packages/event_model/__init__.py", line 852, in fill_event
#     datum_doc = self._datum_cache[datum_id]
# KeyError: 0.0
#
