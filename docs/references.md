# Model references

LadderProof implements original application code around established circuit theory. It does not claim a new DAC architecture or worst-case theorem.

- [Bryant, Tygar and Huang, Geometric Characterization of Series-Parallel Variable Resistor Networks (1993)](https://people.eecs.berkeley.edu/~tygar/papers/Geometric_characterization_of_series-parallel/Bryant_conference.pdf): exact restricted variable-resistor bounds and computational limits for general networks. Their geometric algorithm is distinct from this application's bounded exhaustive corner enumeration. No paper implementation code was copied.
- [Analog Devices, Digital-to-Analog Converters Are a Bit Analog](https://www.analog.com/en/resources/technical-articles/digitaltoanalog-converters-are-a-bit-analog.html): code steps, differential nonlinearity and monotonicity terminology.
- [TI, R2R accuracy and trimming](https://e2e.ti.com/blogs_/archives/b/precisionhub/posts/need-a-higher-accuracy-from-r2r-ladder-based-architecture-try-trimming): matching and major-carry considerations.
- [Analog Devices, R2R deglitching](https://www.analog.com/en/resources/technical-articles/deglitching-techniques-for-highvoltage-r2r-dacs.html): dynamic switching effects that the present static model does not cover.

The separately implemented verifier uses ordinary series/parallel Thevenin reduction. All examples and graphics are generated for this project; no proprietary vendor artwork, datasets or device model code is included. Referenced papers and articles retain their own rights.
