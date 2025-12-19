This is a "throwaway" repo created to play with [strands](https://github.com/strands-agents) and code evolution.

I set up code evolution as a two-agent swarm with researcher and supervisor agents. The researcher modifies and evaluates the code and reports its experience to the supervisor. The supervisor provides guidance without ever looking at the code. Such a setup has been used by other multi-agent systems, including recently, by [Glia](https://arxiv.org/pdf/2510.27176). 

## Running the code

You need access to AWS Bedrock, which is hardcoded as the model endpoint. The model being used is "us.anthropic.claude-sonnet-4-20250514-v1:0". These should be easy to change if needed as strands supports most inference providers.

Run code using

`AWS_PROFILE=<your-aws-profile-name> python code_evolution.py --initial-program examples/sorting_optimization/initial_program.py --evaluator examples/sorting_optimization/evaluator.py  --iterations 10`

The command above will produce output in examples/sorting_optimization/evolution_output_{timestamp}

You can plot the results using

`python plot_evolution_metrics.py examples/sorting_optimization/evolution_output_20251218_205632/programs`

## Totally unscientific comparison with openevolve

Thanks to [openevolve](https://github.com/algorithmicsuperintelligence/openevolve), I could find examples to play with. Two such examples in this repo, examples/function_minimination and examples/circle_packing_with_artifacts, are from openevolve, with some minor changes to remove dependence of openevolve classes. 

As I could run the examples on both openevolve and my code, I was curious how they compare. So, I did a completely unscientific comparison for fun. The two systems are using different models (Sonnet-4 vs an ensemble of Gemini-2.5-flash and Gemini-2.5-flash-lite) and different prompts. 

After cloning openevolve, I ran it with a command like the following: 

`OPENAI_API_KEY=<your-openai-compatible-key> python openevolve-run.py examples/circle_packing_with_artifacts/initial_program.py examples/circle_packing_with_artifacts/evaluator.py --config examples/circle_packing_with_artifacts/config_phase_1.yaml --iterations 100`

I then plotted a comparison with openevolve using:

`python plot_evolution_metrics.py examples/circle_packing_with_artifacts/evolution_output_20251218_150801/programs --openevolve examples/circle_packing_with_artifacts/openevolve_output/checkpoints/checkpoint_100/programs --metric1 sum_radii`

The result looked this like:

![Evolution Metrics Comparison Circle Packing](examples/circle_packing_with_artifacts/metrics_plot.png)

"Main" refers to this repo. Code evolution didn't hit the maximum 100 iterations because it came close to the sum_radii target of 2.635. The agent decided that this was good enough.

The result for function_minimination, which I ran for 25 iteraions, was:

![Evolution Metrics Comparison Function Minimization](examples/function_minimization/metrics_plot.png)

The missing datapoints correspond to iterations where a valid program wasn't produced. 