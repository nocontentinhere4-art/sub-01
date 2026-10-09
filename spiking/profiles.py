"""Task-sized networks. Different sizes have different synapses/checkpoints."""
SIMPLE_NEURONS = 100_000
TRADING_NEURONS = 500_000
NIGHT_NEURONS = 1_000_000


def neurons_for(task):
    if task == "simple":
        return SIMPLE_NEURONS
    if task == "trading":
        return TRADING_NEURONS
    if task == "night":
        return NIGHT_NEURONS
    raise ValueError("unknown brain task")
