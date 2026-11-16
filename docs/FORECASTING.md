# Forecast evaluation methodology

At least 28 complete days of regular readings are required. Input is split chronologically into 60% training, 20% validation and 20% test. No shuffling is used.

The seasonal-naive baseline repeats demand from seven days earlier. Gradient boosting uses scikit-learn `HistGradientBoostingRegressor`, 80 iterations, L2 regularization, and a fixed seed. Candidate tree sizes (7 and 15 leaves) are selected using validation MAE. The selected model is refitted through the validation boundary and evaluated once on the untouched test interval. A final model fitted to all available history generates the requested future horizon.

Features are sine/cosine UTC hour, weekday, a calendar shift indicator, previous-interval demand, previous-day demand and previous-week demand. Every training lag precedes its target. At each forecast origin, multi-step lags are generated recursively from previous predictions, never from held-out target observations. Validation and test predictions therefore represent fixed-origin trajectories rather than teacher-forced one-step scores.

MAE and RMSE are in kW. sMAPE is `200 × mean(|actual−prediction| / max(|actual|+|prediction|, 1e−6))`. Error by UTC hour is the mean absolute error over held-out observations. The UI displays held-out actuals, predictions, baseline, and future demand/solar separately.

Future solar repeats the previous week; tariffs repeat the most recent week. No future weather API is assumed. Temperature is generated in synthetic datasets but is not fed into the current model, avoiding an implicit perfect-weather forecast. Changing production behavior invalidates unchanged-shift assumptions. No calibrated prediction intervals are claimed. Synthetic accuracy is useful for pipeline verification and cannot establish performance at a real factory.

The regression tests record recursive feature inputs to check that later steps use predictions rather than future actuals. Integration tests run the real forecaster through the same persisted job path as the UI, then optimize that forecast.
