class Engine(object):
    def __init__(self, domain, support, weight):
        self.domain = domain
        self.support = support
        self.weight = weight

    def compute_volume(self):
        raise NotImplementedError()

    def compute_probabilities(self, queries):
        volume = self.compute_volume()
        return [self.copy(self.support & query, self.weight).compute_volume() / float(volume) for query in queries]

    def compute_probability(self, query):
        return self.compute_probabilities([query])

    def get_samples(self, n):
        raise NotImplementedError()

    def copy(self, support, weight):
        raise NotImplementedError()

    def bound_tuples(self):
        return tuple(
            ((self.domain.var_domains[var][0], True), (self.domain.var_domains[var][1], True))
            for var in self.domain.real_vars
        )

    def bound_volume(self, bounds=None):
        if bounds is None:
            bounds = self.bound_tuples()

        if bounds is None or len(bounds) == 0:
            return None

        volume = 1
        for lb_bound, ub_bound in bounds:
            volume *= ub_bound[0] - lb_bound[0]
        return volume
