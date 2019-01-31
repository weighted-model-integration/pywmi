import json

from typing import IO, TypeVar, Type

# noinspection PyTypeChecker
T = TypeVar('T', bound='Exportable')


class Exportable:
    def get_state(self) -> dict:
        raise NotImplementedError()

    @classmethod
    def from_state(cls: Type[T], state: dict) -> T:
        raise NotImplementedError()

    def to_file(self, filename: str):
        with open(filename, "w") as ref:
            self.dump(ref)

    def dump(self, ref: IO):
        json.dump(self.get_state(), ref)

    def dumps(self) -> str:
        return json.dumps(self.get_state())

    @classmethod
    def from_file(cls: Type[T], filename: str) -> T:
        with open(filename) as ref:
            return cls.load(ref)

    @classmethod
    def load(cls: Type[T], ref: IO) -> T:
        return cls.from_state(json.load(ref))

    @classmethod
    def loads(cls: Type[T], string: str) -> T:
        return cls.from_state(json.loads(string))
