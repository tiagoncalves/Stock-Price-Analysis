# author: Tiago Santos
# date: 11/16/2019


import requests
import time
import pandas as pd
import numpy as np
import ast
import mysql.connector
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup
from mysql.connector import errorcode
from sqlalchemy import create_engine
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from datetime import datetime


class WebScraper():
    def __init__(self, table_name, db_name):
        self.table_name = table_name
        self.db_name = db_name
        self.__query = (
            "CREATE TABLE IF NOT EXISTS {} ("
            "  `date` bigint(20) NOT NULL,"
            "  `open` float NOT NULL,"
            "  `high` float NOT NULL,"
            "  `low` float NOT NULL,"
            "  `close` float NOT NULL,"
            "  `AdjClose` float NOT NULL,"
            "  `volume` bigint(20) NOT NULL"
            ") ENGINE=InnoDB").format(self.table_name)

        # create the table in the database
        self.__create_table()

    def __dbconnection(self):
        try:
            # create mysql connector
            mydb = mysql.connector.connect(
                user="root",
                host="localhost",
                passwd="root",
                database=self.db_name
            )

            # create mysql cursor
            cursor = mydb.cursor()

            # return the cursor and connector
            return (cursor, mydb)

        # handle the error for name, password and database
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                print("Something is wrong with your user name or password")
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                print("Something is wrong with your database or does not exist")
            else:
                print(err)

    def __create_table(self):
        # create a connection with the database calling the method dbconnection
        cursor, mydb = self.__dbconnection()

        # execute the query
        cursor.execute(self.__query)

        # close the connections
        cursor.close()
        mydb.close()

    def scrape_data(self, url):
        # extract the html data from a webpage
        page = requests.get(url)
        soup = BeautifulSoup(page.text, 'html.parser')

        # split the data to get just the stock Historical Price
        text_split_initial = soup.text.split("""HistoricalPriceStore""")[1]
        text_split_final = text_split_initial.split("isPending")[0][13:-3]

        # create a tuple with json stock information
        stockdata = ast.literal_eval(text_split_final)

        # create a data frame from the stock tuple data
        df_stock = pd.DataFrame.from_dict(stockdata)

        # connect to the database
        db = ('mysql://root:root@localhost/{}').format(self.db_name)
        mydb = create_engine(db)

        # update the database with the data frame
        df_stock.to_sql(self.table_name, con=mydb, if_exists='replace', index=False)

    def __str__(self):
        return 'Database name: ' + self.db_name + ', Table name: ' + self.table_name


class StockPricePrediction(WebScraper):
    def regression(self):
        # connect to the database
        db = ('mysql://root:root@localhost/{}').format(self.db_name)
        mydb = create_engine(db)

        # retrieve the stock information from the database and create a data frame
        query = ('SELECT date,close FROM {} ORDER BY date').format(self.table_name)
        df_stock = pd.read_sql_query(query, mydb)

        # check data types in columns
        # df_stock.info()

        # check for missing values in the columns
        # df_stock.isna().values.any()

        # split data into train and test set: 80% / 20%
        train, test = train_test_split(df_stock, test_size=0.20)

        # create train arrays
        # reshape index column to 1D array for .fit() method
        X_train = np.array(train['date']).reshape(-1, 1)
        y_train = train['close']

        # create LinearRegression Object
        self.model = LinearRegression()
        # fit linear model using the train data set
        self.model.fit(X_train, y_train)

        # create test arrays
        X_test = np.array(test['date']).reshape(-1, 1)
        y_test = test['close']

        # generate array with predicted values
        y_pred = self.model.predict(X_test)

        # plot the graph
        self.__plot(X_test, y_test, y_pred)

    def __plot(self, X_test, y_test, y_pred):
        # convert the date format from unix timestamp to YYYY-MM-DD to be used in the plot
        date_lst = []
        for i in range(len(X_test)):
            date = time.localtime(X_test[i])[0:3]
            date_str = str(date[0]) + "-" + str(date[1]) + "-" + str(date[2])
            date_time = datetime.strptime(date_str, '%Y-%m-%d')
            date_lst.append(date_time.date())
        date_plot = np.array(date_lst).reshape(-1, 1)

        # fix problem between pandas and matplot
        pd.plotting.register_matplotlib_converters()

        # plot fitted line, y test
        plt.figure(1, figsize=(16, 10))
        title = ('Linear Regression | {}').format(self.table_name)
        plt.title(title)
        plt.plot(date_plot, y_pred, color='sienna', label='Predicted Price')
        plt.scatter(date_plot, y_test, color='royalblue', label='Actual Price')

        plt.xlabel('Date')
        plt.ylabel('Stock Price in $')
        plt.legend(loc=4)

        plt.show()

    def prediction(self, date):
        # check the stock price to a specific date
        # the date is reshape to unix timestamp
        datetime_obj = np.array(time.mktime(datetime.strptime(date, '%m/%d/%Y').timetuple())).reshape(-1, 1)
        print("The price prediction for %s stock at %s is $ %5.2f"\
              % (str(self.table_name), date, self.model.predict(datetime_obj)[0]))


if __name__ == "__main__":
    db_name = "stock"
    table_name = ['facebook','tesla','paypal']
    url = ["https://finance.yahoo.com/quote/FB/history?period1=1337324400&period2=1572940800&interval=\
            1d&filter=history&frequency=1d",
           "https://finance.yahoo.com/quote/TSLA/history?period1=1277794800&period2=1573545600&interval=\
                       1d&filter=history&frequency=1d",
           "https://finance.yahoo.com/quote/PYPL/history?period1=1436166000&period2=1573545600&interval=\
           1d&filter=history&frequency=1d"
           ]

    # create the objects of StockPricePrediction
    WS = [StockPricePrediction(table_name[i], db_name) for i in range(len(table_name))]
    for i in range(len(WS)):
        WS[i].scrape_data(url[i])
        WS[i].regression()

    # run the stock price prediction for different dates as long as the user wants
    while True:

        # user choose which stock to run the prediction from the available options
        while True:
            stock = input("Choose from facebook, tesla or paypal to predict stock price: ")
            if stock.strip().lower() == 'facebook':
                WS_object = WS[0]
                break
            elif stock.strip().lower() == 'tesla':
                WS_object = WS[1]
                break
            elif stock.strip().lower() == 'paypal':
                WS_object = WS[2]
                break
            else:
                print("Invalid option entered")

        # user choose which date to run the prediction
        while True:
            date = input("Enter the date for the price prediction (MM/DD/YYYY):")
            try:
                datetime.strptime(date, '%m/%d/%Y')
                break
            except ValueError:
                print("Incorrect data format, should be MM/DD/YYYY")

        # run the stock price prediction for the request date
        WS_object.prediction(date)

        # continue the program or stop if the user requests
        text = input("\nDo you want to perform other stock price prediction (y/n)?")
        if text.strip().lower() == 'n':
            break