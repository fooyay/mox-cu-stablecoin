# Moccasin Stablecoin Project

🐍 Welcome to my Moccasin Stablecoin project!

## Quickstart

1. Deploy to a fake local network that titanoboa automatically spins up!

```bash
mox run deploy
```

2. Run tests

```
mox test
```

_For documentation, please run `mox --help` or visit [the Moccasin documentation](https://cyfrin.github.io/moccasin)_

## Stablecoin

- Users can deposit $200 of ETH
- They can then mint $50 of Stablecoin
  - This means they will have a 4/1 ratio of collateral to stablecoin, which is very safe!
  - We will set the required collateral ratio to 2/1
- If the price of ETH drops, for example to $50, others should  be able to liquidate those users.


# Additional docs to be done:
# how to run
# update doc strings
# write docs
