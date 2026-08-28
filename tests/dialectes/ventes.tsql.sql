-- SQL Server (tsql) dialect fixture: [bracket] identifiers, [dbo] schema,
-- IDENTITY, inline PRIMARY KEY and FOREIGN KEY constraints.
CREATE TABLE [dbo].[Customer] (
    [CustomerID] INT IDENTITY(1,1) NOT NULL,
    [Name] NVARCHAR(120) NOT NULL,
    [Email] NVARCHAR(200),
    CONSTRAINT [PK_Customer] PRIMARY KEY ([CustomerID])
);

CREATE TABLE [dbo].[Order] (
    [OrderID] INT IDENTITY(1,1) NOT NULL,
    [CustomerID] INT NOT NULL,
    [Total] DECIMAL(10,2),
    CONSTRAINT [PK_Order] PRIMARY KEY ([OrderID]),
    CONSTRAINT [FK_Order_Customer] FOREIGN KEY ([CustomerID])
        REFERENCES [dbo].[Customer] ([CustomerID])
);
