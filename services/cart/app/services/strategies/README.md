# Strategy Pattern Implementation in Cart Service

## Overview

This directory contains the implementation of the Strategy Design Pattern in the Cart Service. The strategy pattern is used to define a family of algorithms, encapsulate each one, and make them interchangeable. This allows the algorithms to vary independently from the clients that use them.

## Strategy Types

The Cart Service implements three main strategy types:

### 1. Sales Promotion Strategies

Located in `strategies/sales_promo/` directory, these strategies handle different types of sales promotions that can be applied to a cart. Currently includes:
- SalesPromoSample (basic promotion implementation)

### 2. Payment Strategies

Located in `strategies/payments/` directory, these strategies handle different payment methods:
- Cash payment (`cash.py`)
- Cashless payment like credit/debit cards (`cashless.py`)
- Other payment methods like gift cards (`others.py`)

Each payment method has its own validation rules and processing logic while sharing common functionality through the abstract base class.

`pay(cart_doc, payment_code, amount, detail=None, **kwargs)` and `refund(cart_doc, payment_code, amount, detail=None, **kwargs)` are both `async`. They must accept keyword arguments beyond these parameters. A strategy may ignore a keyword that does not change what is settled. When a keyword carries a value the strategy cannot honour, it refuses the payment instead of dropping the value.

### 3. Receipt Data Strategies

Located in `strategies/receipt_data/` directory, these strategies handle different formats and content for receipt generation.

## Configuration: plugins.json

The `plugins.json` file in the cart directory is a configuration file that defines which strategy implementations should be loaded by the `CartStrategyManager`. This allows for dynamic loading of strategies without modifying code.

### Structure

```json
{
  "sales_promo_strategies": [
    {
      "class_name": "SalesPromoSample",
      "module_name": "app.services.strategies.promotions.sales_promo_sample",
      "parameters": ["01"]
    }
  ],
  "payment_strategies": [
    {
      "class_name": "PaymentByCash",
      "module_name": "app.services.strategies.payments.cash",
      "parameters": ["01"]
    },
    {
      "class_name": "PaymentByCashless",
      "module_name": "app.services.strategies.payments.cashless",
      "parameters": ["11"]
    },
    {
      "class_name": "PaymentByOthers",
      "module_name": "app.services.strategies.payments.others",
      "parameters": ["12"]
    }
  ],
  "receipt_data_strategies": [
    {
      "class_name": "ReceiptDataSample",
      "module_name": "app.services.strategies.receipts.receipt_data_sample",
      "parameters": []
    }
  ]
}
```

### Configuration Fields

For each strategy:

- `module`: The Python module path where the class is located
- `class`: The name of the class that implements the strategy (or `function`, for a plain function)
- `args`: Positional arguments passed to the class constructor (a payment strategy takes its payment code)
- `kwargs`: Keyword arguments passed to the class constructor

The manager reads only these keys and only the groups this service uses (`sales_promo_strategies`, `payment_strategies`, `receipt_data_strategies`). Anything else in the file is ignored.

### Adding New Strategies

To add a new strategy:

1. Create a new class that extends the appropriate abstract base class
2. Add your implementation to the plugins.json file with the correct class name, module path, and parameters

The CartStrategyManager will automatically load your new strategy at runtime.

## How the Strategy Manager Works

The `CartStrategyManager` class (in `cart_strategy_manager.py`) is responsible for:

1. Reading the plugins.json configuration file
2. Dynamically loading the specified strategy classes
3. Instantiating strategy objects with the provided parameters
4. Making strategies available to the CartService for use at runtime

This approach provides extensibility without modifying existing code, following the Open-Closed Principle of SOLID design.